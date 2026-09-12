"""Re-enqueue onboarded notices for published source_intakes.

Scans published intakes that carry a contact email and enqueues the notice their
current state should have produced. Pass ``--intake-id`` to target one intake (used
to resend a wrong message) and ``--replace`` to drop its previous notice first.
"""
from __future__ import annotations

import argparse
import os
import sys
from sqlalchemy import text

from common import session_for, utcnow
from publish_catalog import enqueue_published_intake_notifications


def backfill_intakes(db_url: str, *, intake_id: int | None = None, replace: bool = False) -> int:
    db = session_for(db_url)
    try:
        where = (
            "status = 'published' AND contact_email IS NOT NULL AND TRIM(contact_email) != ''"
        )
        params: dict[str, object] = {}
        if intake_id is not None:
            where += " AND id = :intake_id"
            params["intake_id"] = intake_id
        rows = db.execute(text(
            f"SELECT id, product_count, finished_at FROM source_intakes WHERE {where} ORDER BY id ASC"
        ), params).mappings().all()

        now = utcnow()
        count = 0
        for r in rows:
            target_id = r["id"]
            product_count = r["product_count"] or 0
            published_at = r["finished_at"] or now
            if replace:
                # Only one notice should exist per intake; removing it lets the fixed
                # template replace the message that was already delivered.
                db.execute(text(
                    "DELETE FROM notification_outbox WHERE dedupe_key LIKE :prefix"
                ), {"prefix": f"source-intake:{target_id}:shop_intake.%"})
            enqueue_published_intake_notifications(
                db,
                intake_id=target_id,
                intake_status="published",
                product_count=product_count,
                published_at=published_at,
            )
            count += 1
        db.commit()
        print(f"Scanned {len(rows)} published intakes with contact email; processed backfill.")
        return count
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enqueue onboarded notices for published intakes")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--intake-id", type=int, help="Only process this intake id")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete the intake's existing notice so the regenerated one is sent instead",
    )
    args = parser.parse_args()
    if not args.database_url:
        print("--database-url or DATABASE_URL is required", file=sys.stderr)
        raise SystemExit(1)
    backfill_intakes(args.database_url, intake_id=args.intake_id, replace=args.replace)
