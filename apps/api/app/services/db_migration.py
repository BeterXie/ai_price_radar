from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _ensure_sqlite_offer_click_indexes(conn) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_offer_id ON offer_clicks(offer_id)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_shop_id ON offer_clicks(shop_id)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_user_id ON offer_clicks(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_product_slug ON offer_clicks(product_slug)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_ip_hash ON offer_clicks(ip_hash)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_created_at ON offer_clicks(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_shop_created ON offer_clicks(shop_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_offer_clicks_ip_dedup ON offer_clicks(offer_id, ip_hash, created_at)",
    ]
    for statement in statements:
        conn.execute(text(statement))


def _rebuild_sqlite_offer_clicks(conn, existing_cols: set[str]) -> None:
    logger.info("Rebuilding offer_clicks to add the user foreign key")
    conn.execute(text("DROP TABLE IF EXISTS offer_clicks_migration"))
    conn.execute(text(
        """
        CREATE TABLE offer_clicks_migration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER,
            shop_id INTEGER NOT NULL,
            user_id INTEGER,
            product_slug VARCHAR(160),
            ip_hash VARCHAR(64) DEFAULT '',
            user_agent TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(offer_id) REFERENCES offers(id) ON DELETE CASCADE,
            FOREIGN KEY(shop_id) REFERENCES shops(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    ))
    source_expressions = {
        "id": "id",
        "offer_id": "offer_id" if "offer_id" in existing_cols else "NULL",
        "shop_id": "shop_id",
        "user_id": "user_id" if "user_id" in existing_cols else "NULL",
        "product_slug": "product_slug" if "product_slug" in existing_cols else "NULL",
        "ip_hash": "COALESCE(ip_hash, '')" if "ip_hash" in existing_cols else "''",
        "user_agent": "COALESCE(user_agent, '')" if "user_agent" in existing_cols else "''",
        "created_at": "COALESCE(created_at, CURRENT_TIMESTAMP)" if "created_at" in existing_cols else "CURRENT_TIMESTAMP",
    }
    columns = list(source_expressions)
    conn.execute(text(
        f"INSERT INTO offer_clicks_migration ({', '.join(columns)}) "
        f"SELECT {', '.join(source_expressions[column] for column in columns)} FROM offer_clicks"
    ))
    conn.execute(text("DROP TABLE offer_clicks"))
    conn.execute(text("ALTER TABLE offer_clicks_migration RENAME TO offer_clicks"))
    _ensure_sqlite_offer_click_indexes(conn)


# Standard products retired from the public catalog. Historical rows stay in
# the database for audit, but they must never be listed or classified again.
RETIRED_PRODUCT_SLUGS = ("zhipu-qingyan-vip", "zhipu-api-credit", "zhipu-account")


def _hide_retired_products(conn) -> None:
    from sqlalchemy import inspect

    if "products" not in inspect(conn).get_table_names():
        return
    for slug in RETIRED_PRODUCT_SLUGS:
        conn.execute(
            text("UPDATE products SET is_visible = :hidden WHERE slug = :slug AND is_visible = :visible"),
            {"slug": slug, "hidden": False, "visible": True},
        )


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
            return
        _hide_retired_products(conn)


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
            ("password_hash", "TEXT DEFAULT ''"),
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
        foreign_keys = conn.execute(text("PRAGMA foreign_key_list(offer_clicks)")).fetchall()
        has_user_foreign_key = any(
            row[2] == "users" and row[3] == "user_id" and str(row[6]).upper() == "SET NULL"
            for row in foreign_keys
        )
        if "user_id" not in existing_cols or not has_user_foreign_key:
            _rebuild_sqlite_offer_clicks(conn, existing_cols)
        else:
            _ensure_sqlite_offer_click_indexes(conn)

    # 3b. offers table columns (click tracking added in v17)
    if "offers" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(offers)")).fetchall()}
        if "click_count" not in existing_cols:
            logger.info("Adding column click_count to offers table")
            conn.execute(text("ALTER TABLE offers ADD COLUMN click_count INTEGER DEFAULT 0 NOT NULL"))

    # 3c. auth_codes table columns (verify attempt counting)
    if "auth_codes" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(auth_codes)")).fetchall()}
        if "attempts" not in existing_cols:
            logger.info("Adding column attempts to auth_codes table")
            conn.execute(text("ALTER TABLE auth_codes ADD COLUMN attempts INTEGER DEFAULT 0 NOT NULL"))

    # 3d. reports table columns (verified product context)
    if "reports" in tables:
        existing_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(reports)")).fetchall()}
        if "product_slug" not in existing_cols:
            logger.info("Adding column product_slug to reports table")
            conn.execute(text("ALTER TABLE reports ADD COLUMN product_slug VARCHAR(160)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_product_slug ON reports(product_slug)"))

    # 4. admin_broadcasts table
    if "admin_broadcasts" not in tables:
        logger.info("Creating table admin_broadcasts")
        conn.execute(text(
            """
            CREATE TABLE admin_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_key VARCHAR(64) NOT NULL,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                channels JSON DEFAULT '[]',
                target_user_count INTEGER DEFAULT 0,
                email_sent_count INTEGER DEFAULT 0,
                bot_sent_count INTEGER DEFAULT 0,
                status VARCHAR(30) DEFAULT 'sent',
                created_by VARCHAR(100) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_admin_broadcasts_created_at "
            "ON admin_broadcasts(created_at)"
        ))

    broadcast_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(admin_broadcasts)")).fetchall()}
    if "operation_key" not in broadcast_cols:
        conn.execute(text("ALTER TABLE admin_broadcasts ADD COLUMN operation_key VARCHAR(64)"))
    conn.execute(text(
        "UPDATE admin_broadcasts SET operation_key = 'legacy-' || id "
        "WHERE operation_key IS NULL OR operation_key = ''"
    ))
    conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_broadcasts_operation_key "
        "ON admin_broadcasts(operation_key)"
    ))

    if "user_bot_bindings" in tables:
        duplicates = conn.execute(text(
            "SELECT channel, target_id, MAX(id) AS keep_id "
            "FROM user_bot_bindings "
            "WHERE target_id IS NOT NULL "
            "GROUP BY channel, target_id HAVING COUNT(*) > 1"
        )).fetchall()
        for channel, target_id, keep_id in duplicates:
            conn.execute(text(
                "DELETE FROM user_bot_bindings "
                "WHERE channel = :channel AND target_id = :target_id AND id <> :keep_id"
            ), {"channel": channel, "target_id": target_id, "keep_id": keep_id})
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_bot_binding_target "
            "ON user_bot_bindings(channel, target_id)"
        ))


def _migrate_postgres(conn) -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(64) DEFAULT '';",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_duration_seconds INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS button_click_count INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT DEFAULT '';",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64) DEFAULT '';",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT DEFAULT '';",
        "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;",
        "ALTER TABLE offer_clicks ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0 NOT NULL;",
        "ALTER TABLE auth_codes ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0 NOT NULL;",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS product_slug VARCHAR(160);",
        "CREATE INDEX IF NOT EXISTS ix_reports_product_slug ON reports(product_slug);",
        """
        DELETE FROM user_bot_bindings duplicate
        USING user_bot_bindings keeper
        WHERE duplicate.channel = keeper.channel
          AND duplicate.target_id = keeper.target_id
          AND duplicate.id < keeper.id;
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_bot_binding_target ON user_bot_bindings(channel, target_id);",
        """
        CREATE TABLE IF NOT EXISTS admin_broadcasts (
            id SERIAL PRIMARY KEY,
            operation_key VARCHAR(64),
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
        "ALTER TABLE admin_broadcasts ADD COLUMN IF NOT EXISTS operation_key VARCHAR(64);",
        "UPDATE admin_broadcasts SET operation_key = 'legacy-' || id WHERE operation_key IS NULL OR operation_key = '';",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_broadcasts_operation_key ON admin_broadcasts(operation_key);",
        "ALTER TABLE admin_broadcasts ALTER COLUMN operation_key SET NOT NULL;",
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'source_intakes') THEN
                ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_type;
                ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
                    CHECK (source_type::text = ANY (ARRAY['unknown', 'ldxp', 'merchant_json', 'dujiao_next', 'woocommerce', '16688', 'schema_org', 'acg_faka', 'other']));
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'source_candidates') THEN
                ALTER TABLE source_candidates DROP CONSTRAINT IF EXISTS ck_source_candidates_platform;
                ALTER TABLE source_candidates ADD CONSTRAINT ck_source_candidates_platform
                    CHECK (detected_platform::text = ANY (ARRAY['unknown', 'ldxp', 'dujiao_next', 'merchant_json', 'woocommerce', '16688', 'schema_org', 'acg_faka', 'other']));
            END IF;
        END $$;
        """,
    ]
    for stmt in statements:
        conn.execute(text(stmt))
