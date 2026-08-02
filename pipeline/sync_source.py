from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import ImportLockUnavailable, session_for
from connectors import CONNECTORS
from publish_catalog import (
    SourceSpec,
    UNREVIEWED_DUJIAO_ENV,
    publish_sources,
    validate_dujiao_source_access,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compatibility publisher for one source. It carries the current catalog forward so other sources are not "
            "overwritten; use publish_catalog.py for authoritative multi-source publication."
        )
    )
    parser.add_argument("--connector", required=True, choices=sorted(CONNECTORS))
    parser.add_argument("--source", required=True, help="Connector source path or HTTPS URL")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument(
        "--review-db",
        type=Path,
        help="Discovery SQLite database required to publish an approved Dujiao-Next source",
    )
    parser.add_argument(
        "--allow-unreviewed-source",
        action="store_true",
        help=f"Development only; also requires {UNREVIEWED_DUJIAO_ENV}=1",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.connector == "ldxp" and not Path(args.source).exists():
        parser.error(f"source db not found: {args.source}")
    if args.connector == "dujiao-next":
        if args.review_db is not None and not args.review_db.is_file():
            parser.error(f"review db not found: {args.review_db}")
        try:
            validate_dujiao_source_access(
                args.source,
                review_db=args.review_db,
                allow_unreviewed=args.allow_unreviewed_source,
            )
        except ValueError as exc:
            parser.error(str(exc))

    db = session_for(args.database_url)
    try:
        result = publish_sources(
            db,
            [SourceSpec(args.connector, args.source)],
            source_label=args.connector,
            carry_forward_current=True,
            dry_run=args.dry_run,
        )
    except ImportLockUnavailable as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3
    except Exception as exc:
        print(json.dumps({"error": str(exc), "published": False}, ensure_ascii=False))
        return 2
    finally:
        db.close()
    imported = result.imports[0]
    print(json.dumps({
        "connector": imported.connector,
        "total": imported.total,
        "created": imported.created,
        "changed": imported.changed,
        "failed": 0,
        "dry_run": args.dry_run,
        "snapshot_id": result.snapshot_id,
        "offer_count": result.offer_count,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
