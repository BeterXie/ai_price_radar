from __future__ import annotations

import argparse
import os
import sqlite3

try:
    import psycopg
except ImportError:
    psycopg = None


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS shop_coupons (
    id BIGSERIAL PRIMARY KEY,
    coupon_batch_id BIGINT DEFAULT 0,
    name VARCHAR(120) NOT NULL,
    code VARCHAR(64) NOT NULL UNIQUE,
    discount_amount NUMERIC(10, 2) NOT NULL,
    min_spend NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    shop_name VARCHAR(100) NOT NULL DEFAULT '彩头AI',
    shop_url TEXT NOT NULL DEFAULT 'https://wzyp.cn/shop/pricememo',
    is_assigned BOOLEAN NOT NULL DEFAULT false,
    assigned_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_shop_coupons_assigned_user ON shop_coupons(assigned_user_id);
CREATE INDEX IF NOT EXISTS ix_shop_coupons_unassigned ON shop_coupons(is_assigned, expires_at);
CREATE INDEX IF NOT EXISTS ix_shop_coupons_code ON shop_coupons(code);

CREATE TABLE IF NOT EXISTS coupon_campaigns (
    id BIGSERIAL PRIMARY KEY,
    campaign_code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(120) NOT NULL,
    coupon_batch_id BIGINT DEFAULT 0,
    max_per_user INT NOT NULL DEFAULT 1,
    total_quota INT NOT NULL DEFAULT 100,
    claimed_count INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_coupon_campaigns_code ON coupon_campaigns(campaign_code);
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS shop_coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_batch_id INTEGER DEFAULT 0,
    name VARCHAR(120) NOT NULL,
    code VARCHAR(64) NOT NULL UNIQUE,
    discount_amount NUMERIC(10, 2) NOT NULL,
    min_spend NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    shop_name VARCHAR(100) NOT NULL DEFAULT '彩头AI',
    shop_url TEXT NOT NULL DEFAULT 'https://wzyp.cn/shop/pricememo',
    is_assigned BOOLEAN NOT NULL DEFAULT 0,
    assigned_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_shop_coupons_assigned_user ON shop_coupons(assigned_user_id);
CREATE INDEX IF NOT EXISTS ix_shop_coupons_unassigned ON shop_coupons(is_assigned, expires_at);
CREATE INDEX IF NOT EXISTS ix_shop_coupons_code ON shop_coupons(code);

CREATE TABLE IF NOT EXISTS coupon_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(120) NOT NULL,
    coupon_batch_id INTEGER DEFAULT 0,
    max_per_user INTEGER NOT NULL DEFAULT 1,
    total_quota INTEGER NOT NULL DEFAULT 100,
    claimed_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_coupon_campaigns_code ON coupon_campaigns(campaign_code);
"""


def migrate_postgres(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_DDL)


def migrate_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SQLITE_DDL)
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create shop coupons and campaigns tables v16")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not db_url:
        parser.error("--database-url or DATABASE_URL is required")

    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        migrate_sqlite(db_path)
        print("Shop coupons v16 SQLite migration complete.")
        return 0

    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL migrations")

    with psycopg.connect(connection_url(db_url)) as connection:
        migrate_postgres(connection)
        connection.commit()
    print("Shop coupons v16 PostgreSQL migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
