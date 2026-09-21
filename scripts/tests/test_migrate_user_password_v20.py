from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from scripts.migrate_user_password_v20 import (
    POSTGRES_DDL,
    migrate_postgres,
    migrate_sqlite,
    sqlite_path_from_url,
)


def _users_columns(db_file: str) -> set[str]:
    conn = sqlite3.connect(db_file)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users);")
        return {row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def test_user_password_v20_ddl_statements():
    assert "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash" in POSTGRES_DDL


def test_user_password_v20_sqlite_adds_column_idempotently(tmp_path):
    db_file = tmp_path / "test_migration.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(200), nickname VARCHAR(100) DEFAULT '');"
    )
    conn.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com');")
    conn.commit()
    conn.close()

    assert "password_hash" not in _users_columns(str(db_file))
    migrate_sqlite(str(db_file))
    assert "password_hash" in _users_columns(str(db_file))
    # Existing rows keep working and default to empty (password not set).
    conn = sqlite3.connect(str(db_file))
    value = conn.execute("SELECT password_hash FROM users WHERE id = 1;").fetchone()[0]
    conn.close()
    assert value in ("", None)

    # Idempotent: running twice must not fail.
    migrate_sqlite(str(db_file))
    assert "password_hash" in _users_columns(str(db_file))


def test_user_password_v20_sqlite_without_users_table_is_noop(tmp_path):
    db_file = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE shops (id INTEGER PRIMARY KEY);")
    conn.commit()
    conn.close()
    migrate_sqlite(str(db_file))  # must not raise


def test_user_password_v20_postgres_execution():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    migrate_postgres(conn)
    assert cursor.execute.call_count == 1
    assert "password_hash" in cursor.execute.call_args[0][0]


def test_user_password_v20_sqlite_path_from_url():
    # 3 slashes = relative path (the leading "/" must be stripped, otherwise it
    # resolves against the filesystem root); 4 slashes = absolute path.
    assert sqlite_path_from_url("sqlite:///./price_radar.db") == "./price_radar.db"
    assert sqlite_path_from_url("sqlite:///price_radar.db") == "price_radar.db"
    assert sqlite_path_from_url("sqlite:////data/app.db") == "/data/app.db"
    assert sqlite_path_from_url("postgresql://user@host/db") is None


def test_legacy_v18_v19_helpers_parse_relative_sqlite_urls():
    """v18/v19 share the same helper; the relative-URL fix must hold there too."""
    from scripts.migrate_coupon_shop_binding_v19 import sqlite_path_from_url as v19
    from scripts.migrate_shop_coupon_campaign_v18 import sqlite_path_from_url as v18

    for helper in (v18, v19):
        assert helper("sqlite:///./price_radar.db") == "./price_radar.db"
        assert helper("sqlite:////data/app.db") == "/data/app.db"
