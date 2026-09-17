from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_db_schema(engine: Engine) -> None:
    """Safely inspects and adds missing columns and tables for SQLite or Postgres."""
    dialect_name = engine.dialect.name
    with engine.begin() as conn:
        if dialect_name == "sqlite":
            _migrate_sqlite(conn)
        elif dialect_name in ("postgresql", "postgres"):
            _migrate_postgres(conn)
        else:
            logger.info("Skipping schema auto-migration for dialect %s", dialect_name)


def _migrate_sqlite(conn) -> None:
    # 1. users table columns
    tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
    if "users" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        user_cols_to_add = [
            ("last_login_at", "TIMESTAMP"),
            ("last_login_ip", "VARCHAR(64) DEFAULT ''"),
            ("last_active_at", "TIMESTAMP"),
            ("total_duration_seconds", "INTEGER DEFAULT 0"),
            ("button_click_count", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in user_cols_to_add:
            if col_name not in existing_cols:
                logger.info("Adding column %s to users table", col_name)
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))

    # 2. user_sessions table columns
    if "user_sessions" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(user_sessions)")).fetchall()}
        session_cols_to_add = [
            ("ip_address", "VARCHAR(64) DEFAULT ''"),
            ("user_agent", "TEXT DEFAULT ''"),
            ("last_active_at", "TIMESTAMP"),
        ]
        for col_name, col_type in session_cols_to_add:
            if col_name not in existing_cols:
                logger.info("Adding column %s to user_sessions table", col_name)
                conn.execute(text(f"ALTER TABLE user_sessions ADD COLUMN {col_name} {col_type}"))

    # 3. offer_clicks table columns
    if "offer_clicks" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(offer_clicks)")).fetchall()}
        if "user_id" not in existing_cols:
            logger.info("Adding column user_id to offer_clicks table")
            conn.execute(text("ALTER TABLE offer_clicks ADD COLUMN user_id INTEGER"))

    # 4. admin_broadcasts table
    if "admin_broadcasts" not in tables:
        logger.info("Creating table admin_broadcasts")
        conn.execute(
            text(
                """
                CREATE TABLE admin_broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    channels JSON DEFAULT '[]',
                    target_user_count INTEGER DEFAULT 0,
                    email_sent_count INTEGER DEFAULT 0,
                    bot_sent_count INTEGER DEFAULT 0,
                    status VARCHAR(30) DEFAULT 'sent',
                    created_by VARCHAR(100) DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS ix_admin_broadcasts_created_at ON admin_broadcasts(created_at);
                """
            )
        )


def _migrate_postgres(conn) -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(64) DEFAULT '';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_duration_seconds INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS button_click_count INTEGER DEFAULT 0;",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64) DEFAULT '';",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT DEFAULT '';",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;",
        "ALTER TABLE offer_clicks ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;",
        """
        CREATE TABLE IF NOT EXISTS admin_broadcasts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            channels JSONB DEFAULT '[]'::jsonb,
            target_user_count INTEGER DEFAULT 0,
            email_sent_count INTEGER DEFAULT 0,
            bot_sent_count INTEGER DEFAULT 0,
            status VARCHAR(30) DEFAULT 'sent',
            created_by VARCHAR(100) DEFAULT 'admin',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_admin_broadcasts_created_at ON admin_broadcasts(created_at);",
    ]
    for stmt in statements:
        conn.execute(text(stmt))
