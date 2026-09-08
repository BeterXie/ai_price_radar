"""Scan all published source_intakes with contact_email and enqueue missing shop_intake.onboarded notifications."""
from __future__ import annotations

import os
import sys
from sqlalchemy import text

from common import session_for, utcnow
from publish_catalog import enqueue_published_intake_notifications


def backfill_intakes(db_url: str) -> int:
    db = session_for(db_url)
    try:
        rows = db.execute(text(
            "SELECT id, product_count, finished_at FROM source_intakes "
            "WHERE status = 'published' AND contact_email IS NOT NULL AND TRIM(contact_email) != '' "
            "ORDER BY id ASC"
        )).mappings().all()

        now = utcnow()
        count = 0
        for r in rows:
            intake_id = r["id"]
            product_count = r["product_count"] or 0
            published_at = r["finished_at"] or now
            enqueue_published_intake_notifications(
                db,
                intake_id=intake_id,
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
    db_url = os.getenv("DATABASE_URL")
    if not db_url and len(sys.argv) > 1:
        db_url = sys.argv[1]
    if not db_url:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)
    backfill_intakes(db_url)
