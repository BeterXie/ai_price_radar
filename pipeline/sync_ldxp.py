from __future__ import annotations

import argparse
import os
import json
import sqlite3
from pathlib import Path

from common import ImportLockUnavailable, begin_snapshot, ensure_products, import_lock, session_for, upsert_offer, utcnow


def load_records(path: Path):
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(source_uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT m.*, c.status AS shop_status, c.source_score, c.last_success_at, c.scanned_at
            FROM matches m
            LEFT JOIN candidates c ON c.token = m.token
            ORDER BY m.collected_at
            """
        )
        for row in rows:
            yield dict(row)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import LDXP crawler SQLite into AI Price Radar")
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if not args.source_db.exists():
        parser.error(f"source db not found: {args.source_db}")

    db = session_for(args.database_url)
    created = changed = total = failed = 0
    try:
        with import_lock(db):
            products = ensure_products(db)
            snapshot = begin_snapshot(db, "ldxp")
            for record in load_records(args.source_db):
                total += 1
                try:
                    was_created, was_changed = upsert_offer(db, record, products, snapshot.id)
                    created += int(was_created)
                    changed += int(was_changed)
                    if total % 100 == 0:
                        db.flush()
                except Exception as exc:
                    failed += 1
                    print(json.dumps({"error": str(exc), "record": record.get("product_name")}, ensure_ascii=False))
            if args.dry_run or failed:
                db.rollback()
            else:
                snapshot.offer_count = total
                snapshot.published_at = utcnow()
                db.commit()
    except ImportLockUnavailable as exc:
        db.rollback()
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3
    finally:
        db.close()
    print(json.dumps({"total": total, "created": created, "changed": changed, "failed": failed, "dry_run": args.dry_run}, ensure_ascii=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
