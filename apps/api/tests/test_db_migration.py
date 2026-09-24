from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.services.db_migration import ensure_db_schema


def _sqlite_engine(path: Path):
    return create_engine(f"sqlite:///{path}")


def test_sqlite_migration_creates_broadcast_table_with_required_operation_key(tmp_path: Path):
    engine = _sqlite_engine(tmp_path / "new-schema.db")

    ensure_db_schema(engine)

    with engine.connect() as conn:
        columns = {row[1]: row for row in conn.execute(text("PRAGMA table_info(admin_broadcasts)"))}
        assert columns["operation_key"][3] == 1
        indexes = {row[1]: row for row in conn.execute(text("PRAGMA index_list(admin_broadcasts)"))}
        assert indexes["uq_admin_broadcasts_operation_key"][2] == 1


def test_sqlite_migration_backfills_legacy_broadcast_operation_keys(tmp_path: Path):
    engine = _sqlite_engine(tmp_path / "legacy-broadcast.db")
    with engine.begin() as conn:
        conn.execute(text(
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
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO admin_broadcasts (title, content) VALUES ('legacy', 'body')"
        ))

    ensure_db_schema(engine)

    with engine.begin() as conn:
        assert conn.scalar(text("SELECT operation_key FROM admin_broadcasts WHERE id = 1")) == "legacy-1"
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO admin_broadcasts (operation_key, title, content) "
                "VALUES ('legacy-1', 'duplicate', 'body')"
            ))


def test_sqlite_migration_rebuilds_offer_clicks_with_user_fk_and_index(tmp_path: Path):
    engine = _sqlite_engine(tmp_path / "legacy-clicks.db")
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE shops (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE offers (id INTEGER PRIMARY KEY)"))
        conn.execute(text(
            """
            CREATE TABLE offer_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER,
                shop_id INTEGER NOT NULL,
                product_slug VARCHAR(160),
                ip_hash VARCHAR(64) DEFAULT '',
                user_agent TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        conn.execute(text("INSERT INTO users (id) VALUES (1)"))
        conn.execute(text("INSERT INTO shops (id) VALUES (1)"))
        conn.execute(text("INSERT INTO offers (id) VALUES (1)"))
        conn.execute(text(
            "INSERT INTO offer_clicks (offer_id, shop_id, product_slug, ip_hash) "
            "VALUES (1, 1, 'chatgpt-plus', 'hash')"
        ))

    ensure_db_schema(engine)

    with engine.begin() as conn:
        foreign_keys = conn.execute(text("PRAGMA foreign_key_list(offer_clicks)")).fetchall()
        assert any(
            row[2] == "users" and row[3] == "user_id" and row[6].upper() == "SET NULL"
            for row in foreign_keys
        )
        indexes = {row[1] for row in conn.execute(text("PRAGMA index_list(offer_clicks)"))}
        assert "ix_offer_clicks_user_id" in indexes
        assert conn.scalar(text("SELECT COUNT(*) FROM offer_clicks")) == 1

        conn.execute(text("UPDATE offer_clicks SET user_id = 1 WHERE id = 1"))
        conn.execute(text("DELETE FROM users WHERE id = 1"))
        assert conn.scalar(text("SELECT user_id FROM offer_clicks WHERE id = 1")) is None


def test_sqlite_migration_adds_report_product_context(tmp_path: Path):
    engine = _sqlite_engine(tmp_path / "legacy-reports.db")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE reports ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, offer_id INTEGER, kind VARCHAR(40), "
            "message TEXT NOT NULL, contact VARCHAR(200), status VARCHAR(30), "
            "public_summary TEXT, merchant_response TEXT, resolved_at TIMESTAMP, "
            "created_at TIMESTAMP, updated_at TIMESTAMP)"
        ))

    ensure_db_schema(engine)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(reports)"))}
        indexes = {row[1] for row in conn.execute(text("PRAGMA index_list(reports)"))}
        assert "product_slug" in columns
        assert "ix_reports_product_slug" in indexes


def test_migration_hides_retired_zhipu_products(tmp_path: Path):
    from app.database import Base
    from app.models import Product
    from sqlalchemy.orm import Session

    engine = _sqlite_engine(tmp_path / "retired.db")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Product(slug="zhipu-qingyan-vip", platform="智谱", display_name="智谱清言会员", is_visible=True),
            Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus", is_visible=True),
        ])
        db.commit()

    ensure_db_schema(engine)

    with Session(engine) as db:
        visibility = {product.slug: product.is_visible for product in db.query(Product)}
    assert visibility == {"zhipu-qingyan-vip": False, "chatgpt-plus": True}
