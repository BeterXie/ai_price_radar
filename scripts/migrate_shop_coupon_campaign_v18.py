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


def sqlite_path_from_url(url: str) -> str | None:
    """Extract the file path from a sqlite:// URL (sqlite:///x.db, sqlite:////abs/x.db)."""
    if not url or not url.startswith("sqlite"):
        return None
    prefix = "sqlite+pysqlite://" if url.startswith("sqlite+pysqlite://") else "sqlite://"
    path = url[len(prefix):]
    if path.startswith("/"):
        # sqlite:////data/app.db -> /data/app.db ; sqlite:///./x.db -> ./x.db
        path = path[1:] if url.startswith("sqlite:////") else path
    return path or None


POSTGRES_DDL = """
ALTER TABLE shop_coupons ADD COLUMN IF NOT EXISTS campaign_id BIGINT REFERENCES coupon_campaigns(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_shop_coupons_campaign_id ON shop_coupons(campaign_id);
CREATE INDEX IF NOT EXISTS ix_shop_coupons_user_campaign ON shop_coupons(assigned_user_id, campaign_id);
"""


def migrate_postgres(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_DDL)


def migrate_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(shop_coupons);")
        columns = [row[1] for row in cursor.fetchall()]
        if "campaign_id" not in columns:
            cursor.execute("ALTER TABLE shop_coupons ADD COLUMN campaign_id INTEGER REFERENCES coupon_campaigns(id) ON DELETE SET NULL;")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_shop_coupons_campaign_id ON shop_coupons(campaign_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_shop_coupons_user_campaign ON shop_coupons(assigned_user_id, campaign_id);")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate database to v18: Add campaign_id to shop_coupons.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="SQLite database file (overrides the path in --database-url; default price_radar.db)",
    )
    args = parser.parse_args()

    if args.database_url and (args.database_url.startswith("postgresql://") or args.database_url.startswith("postgresql+psycopg://")):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgreSQL migrations.")
        with psycopg.connect(connection_url(args.database_url)) as connection:
            migrate_postgres(connection)
            connection.commit()
        print("Migrated PostgreSQL database to v18.")
    else:
        # Honor an explicit --sqlite-path first, then a sqlite:// --database-url,
        # and only fall back to the default file name.
        db_path = args.sqlite_path or sqlite_path_from_url(args.database_url or "") or "price_radar.db"
        migrate_sqlite(db_path)
        print(f"Migrated SQLite database to v18: {db_path}")


if __name__ == "__main__":
    main()
