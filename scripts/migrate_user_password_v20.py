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
    if url.startswith("sqlite:////"):
        # sqlite:////data/app.db -> /data/app.db (absolute path, 4 slashes)
        path = path[1:]
    elif path.startswith("/"):
        # sqlite:///./x.db -> ./x.db (relative path, 3 slashes); keeping the
        # leading "/" here would resolve against the filesystem root instead.
        path = path[1:]
    return path or None


POSTGRES_DDL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT DEFAULT '';
"""


def migrate_postgres(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_DDL)


def migrate_sqlite(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(users);")
            cols = [row[1] for row in cursor.fetchall()]
            if "password_hash" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT '';")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate database to v20: Add users.password_hash for password login.")
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
        print("Migrated PostgreSQL database to v20.")
    else:
        # Honor an explicit --sqlite-path first, then a sqlite:// --database-url,
        # and only fall back to the default file name.
        db_path = args.sqlite_path or sqlite_path_from_url(args.database_url or "") or "price_radar.db"
        migrate_sqlite(db_path)
        print(f"Migrated SQLite database to v20: {db_path}")


if __name__ == "__main__":
    main()
