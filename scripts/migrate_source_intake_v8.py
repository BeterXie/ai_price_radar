from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


PREPARE_DDL = """
ALTER TABLE source_intakes ADD COLUMN IF NOT EXISTS declared_platform VARCHAR(30);
ALTER TABLE source_intakes ADD COLUMN IF NOT EXISTS detected_platform VARCHAR(30);

UPDATE source_intakes
SET declared_platform = CASE
        WHEN source_type = 'merchant_feed' THEN 'merchant_json'
        ELSE source_type
    END
WHERE declared_platform IS NULL;

UPDATE source_intakes
SET detected_platform = CASE
        WHEN source_type = 'merchant_feed' THEN 'merchant_json'
        ELSE source_type
    END
WHERE detected_platform IS NULL;

ALTER TABLE source_intakes ALTER COLUMN declared_platform SET DEFAULT 'auto';
ALTER TABLE source_intakes ALTER COLUMN declared_platform SET NOT NULL;
ALTER TABLE source_intakes ALTER COLUMN detected_platform SET DEFAULT 'unknown';
ALTER TABLE source_intakes ALTER COLUMN detected_platform SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_source_intakes_declared_platform
    ON source_intakes (declared_platform);
CREATE INDEX IF NOT EXISTS ix_source_intakes_detected_platform
    ON source_intakes (detected_platform);

ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_type;
ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_status;
"""

FINAL_DDL = """
UPDATE source_intakes SET source_type='merchant_json' WHERE source_type='merchant_feed';
UPDATE source_intakes SET declared_platform='merchant_json' WHERE declared_platform='merchant_feed';
UPDATE source_intakes SET detected_platform='merchant_json' WHERE detected_platform='merchant_feed';

ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type CHECK (
    source_type IN ('unknown', 'ldxp', 'merchant_json', 'dujiao_next', 'other')
);

ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status CHECK (
    status IN (
        'submitted', 'detecting', 'validation_failed', 'pending_review',
        'approved', 'syncing', 'published', 'rejected', 'needs_re_review',
        'disabled', 'queued', 'validating', 'validated', 'onboarded',
        'no_products'
    )
);
"""

DDL = PREPARE_DDL + FINAL_DDL

STATUS_RANK = {
    "published": 100,
    "onboarded": 100,
    "approved": 90,
    "validated": 85,
    "syncing": 80,
    "validating": 80,
    "queued": 75,
    "pending_review": 70,
    "needs_re_review": 60,
    "submitted": 50,
    "detecting": 50,
    "validation_failed": 40,
    "no_products": 40,
    "rejected": 30,
    "disabled": 20,
}


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _first(rows: list[dict[str, Any]], field: str, default: Any = None) -> Any:
    return next((row[field] for row in rows if row.get(field) not in (None, "")), default)


def _joined(rows: list[dict[str, Any]], field: str) -> str:
    values = list(dict.fromkeys(str(row[field]).strip() for row in rows if str(row.get(field) or "").strip()))
    return "\n".join(values)


def _minimum(rows: list[dict[str, Any]], field: str) -> datetime | None:
    values = [row[field] for row in rows if row.get(field) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], field: str) -> datetime | None:
    values = [row[field] for row in rows if row.get(field) is not None]
    return max(values) if values else None


def merge_merchant_intakes(connection: psycopg.Connection) -> int:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT * FROM source_intakes "
            "WHERE source_type IN ('merchant_feed', 'merchant_json') "
            "ORDER BY source_key, id"
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cursor.fetchall():
            grouped[str(row["source_key"])].append(row)

        merged = 0
        for rows in grouped.values():
            ordered = sorted(
                rows,
                key=lambda row: (STATUS_RANK.get(str(row["status"]), 0), row.get("updated_at") or row["created_at"], -row["id"]),
                reverse=True,
            )
            survivor = ordered[0]
            duplicate_ids = [row["id"] for row in ordered[1:]]
            if duplicate_ids:
                cursor.execute("DELETE FROM source_intakes WHERE id = ANY(%s)", (duplicate_ids,))
                merged += len(duplicate_ids)
            cursor.execute(
                """
                UPDATE source_intakes SET
                    source_type='merchant_json',
                    declared_platform=%s,
                    detected_platform='merchant_json',
                    report_id=%s,
                    source_url=%s,
                    shop_name=%s,
                    contact_email=%s,
                    note=%s,
                    origin=%s,
                    status=%s,
                    decision_note=%s,
                    failure_reason=%s,
                    attempt_count=%s,
                    product_count=%s,
                    lease_expires_at=%s,
                    approved_at=%s,
                    started_at=%s,
                    finished_at=%s,
                    created_at=%s,
                    updated_at=%s
                WHERE id=%s
                """,
                (
                    "auto" if any(row.get("declared_platform") == "auto" for row in rows) else "merchant_json",
                    _first(ordered, "report_id"),
                    _first(ordered, "source_url", survivor["source_url"]),
                    _first(ordered, "shop_name", ""),
                    _first(ordered, "contact_email", ""),
                    _joined(ordered, "note"),
                    "manual" if any(row.get("origin") == "manual" for row in rows) else _first(ordered, "origin", "manual"),
                    survivor["status"],
                    _joined(ordered, "decision_note"),
                    _joined(ordered, "failure_reason"),
                    sum(int(row.get("attempt_count") or 0) for row in rows),
                    max(int(row.get("product_count") or 0) for row in rows),
                    survivor.get("lease_expires_at"),
                    _minimum(rows, "approved_at"),
                    _minimum(rows, "started_at"),
                    _maximum(rows, "finished_at"),
                    _minimum(rows, "created_at"),
                    _maximum(rows, "updated_at"),
                    survivor["id"],
                ),
            )
        return merged


def migrate(connection: psycopg.Connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute(PREPARE_DDL)
    merged = merge_merchant_intakes(connection)
    with connection.cursor() as cursor:
        cursor.execute(FINAL_DDL)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Add detected source platforms and expanded intake workflow states")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        merged = migrate(connection)
        connection.commit()
    print(f"source intake v8 migration complete; duplicate merchant intakes merged: {merged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
