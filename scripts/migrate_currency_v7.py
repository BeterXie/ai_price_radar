from __future__ import annotations

import argparse
import os

import psycopg


DDL = """
ALTER TABLE offer_history ADD COLUMN IF NOT EXISTS currency VARCHAR(10) NOT NULL DEFAULT 'CNY';
UPDATE offers SET currency = UPPER(currency) WHERE currency <> UPPER(currency);
"""

CURRENT_OFFER_BACKFILL = """
UPDATE offers AS offer
SET currency = UPPER(raw.raw_json->>'currency')
FROM raw_products AS raw
WHERE offer.raw_product_id = raw.id
  AND UPPER(COALESCE(raw.raw_json->>'currency', '')) IN (
      'CNY', 'USD', 'EUR', 'GBP', 'JPY', 'HKD', 'TWD', 'KRW',
      'SGD', 'AUD', 'CAD', 'CHF', 'NZD', 'THB', 'MYR', 'PHP'
  )
  AND offer.currency <> UPPER(raw.raw_json->>'currency');
"""


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist offer-history currency")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            cursor.execute(CURRENT_OFFER_BACKFILL)
        connection.commit()
    print("currency v7 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
