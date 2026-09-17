from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from scripts.migrate_shop_coupons_v16 import (
    POSTGRES_DDL,
    SQLITE_DDL,
    migrate_postgres,
    migrate_sqlite,
)


def test_shop_coupons_v16_ddl_statements():
    assert "CREATE TABLE IF NOT EXISTS shop_coupons" in POSTGRES_DDL
    assert "CREATE TABLE IF NOT EXISTS coupon_campaigns" in POSTGRES_DDL
    assert "ix_shop_coupons_code" in POSTGRES_DDL

    assert "CREATE TABLE IF NOT EXISTS shop_coupons" in SQLITE_DDL
    assert "CREATE TABLE IF NOT EXISTS coupon_campaigns" in SQLITE_DDL
    assert "ix_shop_coupons_code" in SQLITE_DDL


def test_shop_coupons_v16_sqlite_execution(tmp_path):
    db_file = tmp_path / "test_migration.db"
    migrate_sqlite(str(db_file))

    # Verify tables created
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()

    assert "shop_coupons" in tables
    assert "coupon_campaigns" in tables

    # Verify idempotent
    migrate_sqlite(str(db_file))


def test_shop_coupons_v16_postgres_execution():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    migrate_postgres(conn)
    assert cursor.execute.call_count == 1

