from __future__ import annotations

from unittest.mock import MagicMock

from scripts.migrate_16688_stock_status_v12 import (
    OFFERS_UPDATE_SQL,
    OFFER_HISTORY_UPDATE_SQL,
    migrate,
)


def test_16688_stock_status_v12_sql_queries():
    assert "shop.platform = '16688'" in OFFERS_UPDATE_SQL
    assert "offer.stock_status = 'unknown'" in OFFERS_UPDATE_SQL
    assert "stock_status = 'in_stock'" in OFFERS_UPDATE_SQL
    assert "'out', 'unavailable', 'offline', 'closed'" in OFFERS_UPDATE_SQL
    assert "<> '0'" in OFFERS_UPDATE_SQL

    assert "shop.platform = '16688'" in OFFER_HISTORY_UPDATE_SQL
    assert "history.stock_status = 'unknown'" in OFFER_HISTORY_UPDATE_SQL
    assert "stock_status = 'in_stock'" in OFFER_HISTORY_UPDATE_SQL


def test_16688_stock_status_v12_migrate_execution():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 48
    conn.cursor.return_value.__enter__.return_value = cursor

    offers_updated, history_updated = migrate(conn)

    assert offers_updated == 48
    assert history_updated == 48
    assert cursor.execute.call_count == 2
