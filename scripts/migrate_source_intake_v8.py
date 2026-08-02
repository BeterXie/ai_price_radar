from __future__ import annotations

import argparse
import os

import psycopg


DDL = """
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
ALTER TABLE source_intakes ALTER COLUMN detected_platform SET DEFAULT 'other';
ALTER TABLE source_intakes ALTER COLUMN detected_platform SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_source_intakes_declared_platform
    ON source_intakes (declared_platform);
CREATE INDEX IF NOT EXISTS ix_source_intakes_detected_platform
    ON source_intakes (detected_platform);

ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_type;
ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type CHECK (
    source_type IN ('ldxp', 'merchant_feed', 'merchant_json', 'dujiao_next', 'other')
);

ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_status;
ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status CHECK (
    status IN (
        'submitted', 'detecting', 'validation_failed', 'pending_review',
        'approved', 'syncing', 'published', 'rejected', 'needs_re_review',
        'disabled', 'queued', 'validating', 'validated', 'onboarded',
        'no_products'
    )
);
"""


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add detected source platforms and expanded intake workflow states")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
        connection.commit()
    print("source intake v8 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
