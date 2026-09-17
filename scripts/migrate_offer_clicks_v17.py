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
ALTER TABLE offers ADD COLUMN IF NOT EXISTS click_count BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS offer_clicks (
    id BIGSERIAL PRIMARY KEY,
    offer_id BIGINT REFERENCES offers(id) ON DELETE CASCADE,
    shop_id BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    product_slug VARCHAR(160),
    ip_hash VARCHAR(64) NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_offer_clicks_offer_id ON offer_clicks(offer_id);
CREATE INDEX IF NOT EXISTS ix_offer_clicks_shop_created ON offer_clicks(shop_id, created_at);
CREATE INDEX IF NOT EXISTS ix_offer_clicks_ip_dedup ON offer_clicks(offer_id, ip_hash, created_at);
"""

SQLITE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS offer_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    product_slug VARCHAR(160),
    ip_hash VARCHAR(64) NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_offer_clicks_offer_id ON offer_clicks(offer_id);
CREATE INDEX IF NOT EXISTS ix_offer_clicks_shop_created ON offer_clicks(shop_id, created_at);
CREATE INDEX IF NOT EXISTS ix_offer_clicks_ip_dedup ON offer_clicks(offer_id, ip_hash, created_at);
"""


def migrate_postgres(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_DDL)


def migrate_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Check if click_count column exists in offers table
        cursor.execute("PRAGMA table_info(offers)")
        columns = [row[1] for row in cursor.fetchall()]
        if "click_count" not in columns:
            cursor.execute("ALTER TABLE offers ADD COLUMN click_count INTEGER NOT NULL DEFAULT 0")
        conn.executescript(SQLITE_TABLE_DDL)
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create offer clicks tracking table and offers click_count v17")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not db_url:
        parser.error("--database-url or DATABASE_URL is required")

    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        migrate_sqlite(db_path)
        print("Offer clicks v17 SQLite migration complete.")
        return 0

    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL migrations")

    with psycopg.connect(connection_url(db_url)) as connection:
        migrate_postgres(connection)
        connection.commit()
    print("Offer clicks v17 PostgreSQL migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
