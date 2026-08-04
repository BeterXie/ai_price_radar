from __future__ import annotations

import argparse
import gzip
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
            WHERE s.platform = 'ldxp'
              AND rp.raw_json IS NOT NULL
              AND rp.raw_json::jsonb <> '{}'::jsonb
            """
        )
        return {"postgres_ldxp_nonempty_raw_json": int(cursor.fetchone()[0])}


def _postgres_purge(connection: psycopg.Connection, *, dry_run: bool, commit: bool = True) -> dict[str, int]:
    before = _postgres_counts(connection)
    if dry_run:
        return before
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE raw_products rp
            SET raw_json = '{}'
            FROM shops s
            WHERE s.id = rp.shop_id
              AND s.platform = 'ldxp'
              AND rp.raw_json IS NOT NULL
              AND rp.raw_json::jsonb <> '{}'::jsonb
            """
        )
    if commit:
        connection.commit()
    return before


def _legacy_artifacts(crawler_dir: Path) -> list[Path]:
    candidates = [
        crawler_dir / "browser_state.json",
        crawler_dir / "browser_profile",
    ]
    return [path for path in candidates if path.exists()]


def _remove_tree(path: Path) -> None:
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)

    if path.exists():
        raise RuntimeError(f"artifact still exists after removal: {path}")


def _apply_database_cleanup(
    *,
    crawler_db: Path,
    sqlite_backup: Path,
    postgres_connection: psycopg.Connection,
) -> dict[str, Any]:
    """Run the database cleanup as one recoverable unit.

    PostgreSQL updates first (uncommitted), verified to zero, then SQLite is
    purged and verified, and only then PostgreSQL commits. Any failure rolls
    back PostgreSQL and restores SQLite from the preflight backup.
    """
    try:
        postgres_before = _postgres_purge(
            postgres_connection,
            dry_run=False,
            commit=False,
        )
        postgres_after = _postgres_counts(postgres_connection)
        if postgres_after["postgres_ldxp_nonempty_raw_json"] != 0:
            raise RuntimeError("PostgreSQL raw cleanup verification failed")

        sqlite_before = _sqlite_purge(crawler_db, dry_run=False, backup=False)
        sqlite_after = _sqlite_counts(crawler_db)
        if any(sqlite_after.values()):
            raise RuntimeError("SQLite raw cleanup verification failed")

        postgres_connection.commit()
        return {
            "postgres": postgres_before,
            "postgres_after": postgres_after,
            "sqlite": sqlite_before,
            "sqlite_after": sqlite_after,
            "database_cleanup": "success",
        }
    except Exception:
        try:
            postgres_connection.rollback()
        except Exception:
            pass
        if sqlite_backup.is_file():
            shutil.copyfile(sqlite_backup, crawler_db)
            restored = sqlite3.connect(crawler_db)
            try:
                check = restored.execute("PRAGMA quick_check").fetchone()[0]
            finally:
                restored.close()
            if check != "ok":
                raise RuntimeError("SQLite restore quick_check failed") from None
        raise


def _cleanup_legacy_artifacts(paths: list[Path]) -> dict[str, Any]:
    removed: list[str] = []
    failed: list[dict[str, str]] = []
    for path in paths:
        try:
            _remove_tree(path)
            removed.append(str(path))
        except Exception as exc:
            failed.append({"path": str(path), "error": str(exc)})
    return {
        "removed": removed,
        "failed": failed,
    }


def _verify_gzip(path: Path) -> None:
    with gzip.open(path, "rb") as handle:
        while handle.read(65536):
            pass


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
    legacy = _legacy_artifacts(args.crawler_dir)
    summary["legacy_artifacts"] = [str(path) for path in legacy]

    # ---- Phase A: preflight; nothing is modified before every check passes ----
    sqlite_backup: Path | None = None
    postgres_connection = None
    if args.apply:
        if not args.crawler_db.is_file():
            parser.error(f"crawler database not found: {args.crawler_db}")
        sqlite_backup = _sqlite_backup(args.crawler_db)
        backup_conn = sqlite3.connect(sqlite_backup)
        try:
            check = backup_conn.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            backup_conn.close()
        if check != "ok":
            parser.error(f"SQLite backup quick_check failed: {check}")
        if args.database_url and not args.skip_postgres_backup_check:
            backups_dir = Path("backups")
            recent = [
                path
                for path in backups_dir.glob("price_radar_*.sql.gz")
                if path.stat().st_mtime > time.time() - 3600
            ] if backups_dir.exists() else []
            if not recent:
                parser.error("--apply with PostgreSQL requires a backup created within the last hour (run scripts/backup_postgres.sh); pass --skip-postgres-backup-check only for tests")
            try:
                _verify_gzip(recent[0])
            except (OSError, EOFError) as exc:
                parser.error(f"PostgreSQL backup is not readable: {exc}")
        if args.database_url:
            try:
                postgres_connection = psycopg.connect(connection_url(args.database_url))
                _postgres_counts(postgres_connection)
            except Exception as exc:
                if postgres_connection is not None:
                    postgres_connection.close()
                parser.error(f"PostgreSQL connection check failed: {exc}")

    summary["sqlite_backup"] = str(sqlite_backup) if sqlite_backup else ""

    # ---- Phase B: database cleanup (recoverable) ----
    if args.apply:
        try:
            database_summary = _apply_database_cleanup(
                crawler_db=args.crawler_db,
                sqlite_backup=sqlite_backup,
                postgres_connection=postgres_connection,
            )
        except Exception as exc:
            print(json.dumps({"error": str(exc), "rolled_back": True}, ensure_ascii=False))
            return 2
        summary.update(database_summary)
    else:
        summary["sqlite"] = _sqlite_counts(args.crawler_db)
        if args.database_url:
            with psycopg.connect(connection_url(args.database_url)) as connection:
                summary["postgres"] = _postgres_counts(connection)
            summary["postgres_checked"] = True
        else:
            summary["postgres"] = None
            summary["postgres_checked"] = False

    # ---- Phase C: artifact cleanup (non-recoverable, never rolls back databases) ----
    artifact_summary: dict[str, Any] = {
        "removed": [],
        "failed": [],
    }
    if args.apply:
        artifact_summary = _cleanup_legacy_artifacts(legacy)
        summary["artifact_cleanup"] = "success" if not artifact_summary["failed"] else "partial"
        summary["artifacts_removed"] = artifact_summary["removed"]
        summary["artifact_failures"] = artifact_summary["failed"]
    else:
        summary["artifact_cleanup"] = "dry-run"

    print(json.dumps(summary, ensure_ascii=False))
    if args.apply and artifact_summary["failed"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
