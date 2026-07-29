from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import ImportLockUnavailable, begin_snapshot, ensure_products, import_lock, session_for, upsert_offer, utcnow
from connectors import CONNECTORS, get_connector


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a supported source into AI Price Radar")
    parser.add_argument("--connector", required=True, choices=sorted(CONNECTORS))
    parser.add_argument("--source", required=True, help="Connector source path or HTTPS URL")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.connector == "ldxp" and not Path(args.source).exists():
        parser.error(f"source db not found: {args.source}")

    loader = get_connector(args.connector)
    db = session_for(args.database_url)
    created = changed = total = failed = 0
    try:
        with import_lock(db):
            products = ensure_products(db)
            snapshot = begin_snapshot(db, args.connector)
            for record in loader(args.source):
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
    print(json.dumps({
        "connector": args.connector,
        "total": total,
        "created": created,
        "changed": changed,
        "failed": failed,
        "dry_run": args.dry_run,
    }, ensure_ascii=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
