from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import psycopg

from scripts.migrate_source_intake_v8 import connection_url


def _sqlite_counts(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return {
            "matches_raw_json": int(
                conn.execute("SELECT COUNT(*) FROM matches WHERE raw_json IS NOT NULL AND raw_json <> ''").fetchone()[0]
            ),
            "snapshot_raw_json": int(
                conn.execute("SELECT COUNT(*) FROM product_snapshots WHERE raw_json IS NOT NULL AND raw_json <> ''").fetchone()[0]
            ),
        }
    finally:
        conn.close()


def _sqlite_backup(path: Path) -> Path | None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.pre_purge_{stamp}.db")
    conn = sqlite3.connect(path)
    try:
        backup = sqlite3.connect(target)
        try:
            conn.backup(backup)
        finally:
            backup.close()
    finally:
        conn.close()
    return target


def _sqlite_purge(path: Path, *, dry_run: bool, backup: bool = False) -> dict[str, int]:
    if not path.is_file():
        return {}
    conn = sqlite3.connect(path)
    try:
        before = _sqlite_counts(path)
        if dry_run:
            return before
        backup_path = _sqlite_backup(path) if backup else None
        conn.execute("UPDATE matches SET raw_json = NULL")
        conn.execute("UPDATE product_snapshots SET raw_json = NULL")
        conn.commit()
        quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
        if quick_check != "ok":
            raise RuntimeError(f"SQLite quick_check failed after purge: {quick_check}")
        before["backup"] = str(backup_path) if backup_path else ""
        return before
    finally:
        conn.close()


def _postgres_counts(connection: psycopg.Connection) -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM raw_products rp
            JOIN shops s ON s.id = rp.shop_id
            WHERE s.platform = 'ldxp' AND rp.raw_json IS NOT NULL
            """
        )
        return {"postgres_ldxp_raw_json": int(cursor.fetchone()[0])}


def _postgres_purge(connection: psycopg.Connection, *, dry_run: bool) -> dict[str, int]:
    before = _postgres_counts(connection)
    if dry_run:
        return before
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE raw_products rp
            SET raw_json = '{}'::jsonb
            FROM shops s
            WHERE s.id = rp.shop_id AND s.platform = 'ldxp' AND rp.raw_json IS NOT NULL
            """
        )
    connection.commit()
    return before


def _legacy_artifacts(crawler_dir: Path) -> list[Path]:
    candidates = [
        crawler_dir / "browser_state.json",
        crawler_dir / "browser_profile",
    ]
    return [path for path in candidates if path.exists()]


def _remove_tree(path: Path) -> None:
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge historical LDXP raw payloads and legacy browser artifacts")
    parser.add_argument("--crawler-db", type=Path, default=Path("data/crawler/ldxp_crawler.db"))
    parser.add_argument("--crawler-dir", type=Path, default=Path("data/crawler"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--skip-postgres-backup-check", action="store_true", help="skip the required recent PostgreSQL backup check")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.database_url:
        parser.error("--apply requires --database-url or DATABASE_URL")

    summary: dict[str, Any] = {"dry_run": args.dry_run}
    summary["sqlite"] = _sqlite_purge(args.crawler_db, dry_run=args.dry_run, backup=args.apply)
    legacy = _legacy_artifacts(args.crawler_dir)
    summary["legacy_artifacts"] = [str(path) for path in legacy]
    if args.apply:
        for path in legacy:
            _remove_tree(path)

    if args.database_url:
        if args.apply and not args.skip_postgres_backup_check:
            backups_dir = Path("backups")
            recent = [
                path
                for path in backups_dir.glob("price_radar_*.sql.gz")
                if path.stat().st_mtime > time.time() - 3600
            ] if backups_dir.exists() else []
            if not recent:
                parser.error("--apply with PostgreSQL requires a backup created within the last hour (run scripts/backup_postgres.sh); pass --skip-postgres-backup-check only for tests")
        with psycopg.connect(connection_url(args.database_url)) as connection:
            summary["postgres"] = _postgres_purge(connection, dry_run=args.dry_run)

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
