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
ALTER TABLE shop_coupons ADD COLUMN IF NOT EXISTS shop_id BIGINT REFERENCES shops(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_shop_coupons_shop_id ON shop_coupons(shop_id);

ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS shop_id BIGINT REFERENCES shops(id) ON DELETE SET NULL;
ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS shop_url TEXT;
ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS shop_name VARCHAR(100);
CREATE INDEX IF NOT EXISTS ix_coupon_campaigns_shop_id ON coupon_campaigns(shop_id);

-- Backfill existing shop_coupons
UPDATE shop_coupons sc
SET shop_id = s.id
FROM shops s
WHERE sc.shop_id IS NULL AND (
    sc.shop_url = s.source_url
    OR (s.token = 'pricememo' AND (sc.shop_name = '彩头AI' OR sc.shop_url LIKE '%pricememo%'))
);

-- Backfill existing coupon_campaigns: only campaigns that can be attributed to
-- pricememo by their own link/name. A NULL shop_id does NOT mean pricememo:
-- admins can create campaigns that point at other external shops, so leaving
-- those unbound is safer than forcing them into the wrong shop's coupon pool.
UPDATE coupon_campaigns cc
SET shop_id = s.id,
    shop_url = COALESCE(cc.shop_url, s.source_url),
    shop_name = COALESCE(cc.shop_name, s.name)
FROM shops s
WHERE cc.shop_id IS NULL
  AND s.token = 'pricememo'
  AND (
      cc.shop_url = s.source_url
      OR cc.shop_url LIKE '%pricememo%'
      OR cc.shop_name = '彩头AI'
      OR (cc.shop_url IS NULL AND cc.shop_name IS NULL)
  );
"""


def migrate_postgres(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_DDL)


def migrate_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # shop_coupons
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shop_coupons';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(shop_coupons);")
            sc_cols = [row[1] for row in cursor.fetchall()]
            if "shop_id" not in sc_cols:
                cursor.execute("ALTER TABLE shop_coupons ADD COLUMN shop_id INTEGER REFERENCES shops(id) ON DELETE SET NULL;")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_shop_coupons_shop_id ON shop_coupons(shop_id);")

            # Backfill
            cursor.execute("""
            UPDATE shop_coupons
            SET shop_id = (
                SELECT s.id FROM shops s 
                WHERE s.source_url = shop_coupons.shop_url 
                   OR (s.token = 'pricememo' AND (shop_coupons.shop_name = '彩头AI' OR shop_coupons.shop_url LIKE '%pricememo%'))
                LIMIT 1
            )
            WHERE shop_id IS NULL;
            """)

        # coupon_campaigns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coupon_campaigns';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(coupon_campaigns);")
            cc_cols = [row[1] for row in cursor.fetchall()]
            if "shop_id" not in cc_cols:
                cursor.execute("ALTER TABLE coupon_campaigns ADD COLUMN shop_id INTEGER REFERENCES shops(id) ON DELETE SET NULL;")
            if "shop_url" not in cc_cols:
                cursor.execute("ALTER TABLE coupon_campaigns ADD COLUMN shop_url TEXT;")
            if "shop_name" not in cc_cols:
                cursor.execute("ALTER TABLE coupon_campaigns ADD COLUMN shop_name VARCHAR(100);")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_coupon_campaigns_shop_id ON coupon_campaigns(shop_id);")

            cursor.execute("""
            UPDATE coupon_campaigns
            SET shop_id = (SELECT s.id FROM shops s WHERE s.token = 'pricememo' LIMIT 1),
                shop_url = COALESCE(shop_url, (SELECT s.source_url FROM shops s WHERE s.token = 'pricememo' LIMIT 1)),
                shop_name = COALESCE(shop_name, (SELECT s.name FROM shops s WHERE s.token = 'pricememo' LIMIT 1))
            WHERE shop_id IS NULL
              AND EXISTS (SELECT 1 FROM shops s WHERE s.token = 'pricememo')
              AND (
                  shop_url LIKE '%pricememo%'
                  OR shop_name = '彩头AI'
                  OR (shop_url IS NULL AND shop_name IS NULL)
              );
            """)

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate database to v19: Add shop binding to coupons and campaigns.")
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
        print("Migrated PostgreSQL database to v19.")
    else:
        # Honor an explicit --sqlite-path first, then a sqlite:// --database-url,
        # and only fall back to the default file name.
        db_path = args.sqlite_path or sqlite_path_from_url(args.database_url or "") or "price_radar.db"
        migrate_sqlite(db_path)
        print(f"Migrated SQLite database to v19: {db_path}")


if __name__ == "__main__":
    main()
