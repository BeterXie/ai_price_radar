from __future__ import annotations

import argparse
import os

import psycopg


DDL = """
CREATE TABLE IF NOT EXISTS catalog_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL DEFAULT 'migration',
    offer_count INTEGER NOT NULL DEFAULT 0,
    published_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE offers ADD COLUMN IF NOT EXISTS delivery_type VARCHAR(40) NOT NULL DEFAULT 'unknown';
ALTER TABLE offers ADD COLUMN IF NOT EXISTS is_comparable BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE offers ADD COLUMN IF NOT EXISTS service_period VARCHAR(40) NOT NULL DEFAULT 'unknown';
ALTER TABLE offers ADD COLUMN IF NOT EXISTS warranty VARCHAR(40) NOT NULL DEFAULT 'unknown';
ALTER TABLE offers ADD COLUMN IF NOT EXISTS use_scenarios JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE offers ADD COLUMN IF NOT EXISTS item_fingerprint VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE offers ADD COLUMN IF NOT EXISTS snapshot_id BIGINT NULL;

CREATE INDEX IF NOT EXISTS ix_offers_delivery_type ON offers (delivery_type);
CREATE INDEX IF NOT EXISTS ix_offers_is_comparable ON offers (is_comparable);
CREATE INDEX IF NOT EXISTS ix_offers_service_period ON offers (service_period);
CREATE INDEX IF NOT EXISTS ix_offers_warranty ON offers (warranty);
CREATE INDEX IF NOT EXISTS ix_offers_item_fingerprint ON offers (item_fingerprint);
CREATE INDEX IF NOT EXISTS ix_offers_snapshot_id ON offers (snapshot_id);
CREATE INDEX IF NOT EXISTS ix_catalog_snapshots_published_at ON catalog_snapshots (published_at);
"""


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add catalog snapshot and offer-comparability fields")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    with psycopg.connect(connection_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            cursor.execute("SELECT id FROM catalog_snapshots WHERE published_at IS NOT NULL ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO catalog_snapshots (source, offer_count, published_at) "
                    "SELECT 'migration', count(*), now() FROM offers RETURNING id"
                )
                snapshot_id = cursor.fetchone()[0]
                cursor.execute("UPDATE offers SET snapshot_id = %s WHERE snapshot_id IS NULL", (snapshot_id,))
            cursor.execute(
                "SELECT 1 FROM pg_constraint WHERE conname = 'fk_offers_snapshot_id'"
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE offers ADD CONSTRAINT fk_offers_snapshot_id "
                    "FOREIGN KEY (snapshot_id) REFERENCES catalog_snapshots(id) ON DELETE SET NULL"
                )
        connection.commit()
    print("catalog v4 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
