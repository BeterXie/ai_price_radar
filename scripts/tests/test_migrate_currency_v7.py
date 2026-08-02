from scripts.migrate_currency_v7 import CURRENT_OFFER_BACKFILL, DDL, connection_url


def test_currency_migration_is_idempotent_and_backfills_current_offers():
    assert "ADD COLUMN IF NOT EXISTS currency" in DDL
    assert "raw.raw_json->>'currency'" in CURRENT_OFFER_BACKFILL
    assert "'CNY', 'USD', 'EUR'" in CURRENT_OFFER_BACKFILL
    assert connection_url("postgresql+psycopg://user:pass@db/app") == "postgresql://user:pass@db/app"
