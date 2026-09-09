from __future__ import annotations

import argparse
import os

import psycopg

def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


OFFERS_UPDATE_SQL = """
UPDATE offers AS offer
SET stock_status = 'in_stock',
    updated_at = NOW()
FROM shops AS shop, raw_products AS raw
WHERE offer.shop_id = shop.id
  AND offer.raw_product_id = raw.id
  AND shop.platform = '16688'
  AND offer.stock_status = 'unknown'
  AND LOWER(TRIM(COALESCE(raw.raw_json->>'stock_available_status', ''))) NOT IN ('out', 'unavailable', 'offline', 'closed')
  AND TRIM(COALESCE(raw.raw_json->>'stock_available_quantity', '')) <> '0';
"""

OFFER_HISTORY_UPDATE_SQL = """
UPDATE offer_history AS history
SET stock_status = 'in_stock'
FROM offers AS offer, shops AS shop, raw_products AS raw
WHERE history.offer_id = offer.id
  AND offer.shop_id = shop.id
  AND offer.raw_product_id = raw.id
  AND shop.platform = '16688'
  AND history.stock_status = 'unknown'
  AND LOWER(TRIM(COALESCE(raw.raw_json->>'stock_available_status', ''))) NOT IN ('out', 'unavailable', 'offline', 'closed')
  AND TRIM(COALESCE(raw.raw_json->>'stock_available_quantity', '')) <> '0';
"""


def migrate(connection: psycopg.Connection) -> tuple[int, int]:
    with connection.cursor() as cursor:
        cursor.execute(OFFERS_UPDATE_SQL)
        offers_updated = cursor.rowcount
        cursor.execute(OFFER_HISTORY_UPDATE_SQL)
        history_updated = cursor.rowcount
    return offers_updated, history_updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill 16688 on-demand and recharge stock status to in_stock")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        offers_updated, history_updated = migrate(connection)
        connection.commit()
    print(f"16688 stock status v12 migration complete: updated {offers_updated} offers and {history_updated} history records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
