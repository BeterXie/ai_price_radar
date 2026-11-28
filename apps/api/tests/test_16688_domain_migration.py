import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select, text

from app.services.source_discovery import candidate_key_for

spec = importlib.util.spec_from_file_location(
    "domain_migration", Path(__file__).resolve().parents[3] / "scripts" / "migrate_16688_domain.py",
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
OLD = "https://www.16688.com.cn"
NEW = "https://www.16688.store"


@pytest.fixture(params=["sqlite", "postgresql"])
def domain_db(request):
    base = None
    if request.param == "postgresql":
        if not os.getenv("SITE_TEST_DATABASE_URL"):
            pytest.skip("Disposable PostgreSQL not configured")
        base = create_engine(os.environ["SITE_TEST_DATABASE_URL"])
        schema = "domain_16688_" + uuid4().hex
        with base.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(os.environ["SITE_TEST_DATABASE_URL"], connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine("sqlite://")
    metadata = MetaData()
    extras = {
        "source_intakes": ["source_type", "status", "observed_at"],
        "source_candidates": ["candidate_key", "platform_hint", "status"],
        "shops": ["platform", "token"],
        "raw_products": ["source_product_key"],
        "offers": ["price", "observed_at"],
    }
    tables = {}
    for name, columns in migration.URL_COLUMNS.items():
        tables[name] = Table(name, metadata, Column("id", Integer, primary_key=True),
                             *(Column(key, String, default="") for key in (*columns, *extras.get(name, []))),
                             *( [Column("shop_id", Integer)] if name in {"offers", "raw_products"} else []))
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(tables["source_intakes"].insert(), [
            {"id": 1, "source_type": "16688", "source_url": OLD + "/shop/S1", "source_key": OLD + "/shop/S1", "status": "published"},
            {"id": 2, "source_type": "16688", "source_url": OLD + "/shop/S2", "source_key": OLD + "/shop/S2", "status": "disabled"},
        ])
        conn.execute(tables["source_candidates"].insert(), {
            "id": 1, "canonical_url": OLD + "/shop/S1", "discovered_url": OLD + "/shop/S1",
            "canonical_origin": OLD + "/", "detected_source_url": OLD + "/shop/S1", "detected_source_key": OLD + "/shop/S1",
            "candidate_key": candidate_key_for(OLD + "/shop/S1", "16688"), "platform_hint": "16688", "status": "rejected",
        })
        conn.execute(tables["shops"].insert(), {"id": 1, "source_url": OLD + "/shop/S1", "platform": "16688", "token": "16688-S1"})
        conn.execute(tables["raw_products"].insert(), {"id": 1, "shop_id": 1, "source_url": OLD + "/goods/G1", "source_product_key": "16688:G1"})
        conn.execute(tables["offers"].insert(), {"id": 1, "shop_id": 1, "source_url": OLD + "/goods/G1", "price": "0.30", "observed_at": "2026-11-27T00:00:00Z"})
        conn.execute(tables["ad_slots"].insert(), [
            {"id": 1, "link_url": OLD + "/?ref=kept", "image_url": "https://other.example/logo.png"},
            {"id": 2, "link_url": "https://www.16688.com.cn.evil.example/shop/S1", "image_url": ""},
        ])
    try:
        yield engine, tables
    finally:
        engine.dispose()
        if base:
            with base.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            base.dispose()


def test_domain_migration_is_repeatable_preserves_ids_decisions_and_prices(domain_db):
    engine, tables = domain_db
    counts = migration.migrate(engine)
    assert counts == {name: 2 if name == "source_intakes" else 1 for name in tables}
    with engine.connect() as conn:
        assert conn.scalar(select(tables["shops"].c.source_url)) == OLD + "/shop/S1"
    assert migration.migrate(engine, apply=True) == counts
    assert not any(migration.migrate(engine, apply=True).values())
    with engine.connect() as conn:
        offers = conn.execute(select(tables["offers"])).mappings().one()
        assert (offers["id"], offers["shop_id"], offers["price"], offers["observed_at"]) == (1, 1, "0.30", "2026-11-27T00:00:00Z")
        assert offers["source_url"] == NEW + "/goods/G1"
        assert conn.scalar(select(tables["shops"].c.token)) == "16688-S1"
        assert conn.scalar(select(tables["raw_products"].c.source_product_key)) == "16688:G1"
        assert list(conn.scalars(select(tables["source_intakes"].c.status).order_by(tables["source_intakes"].c.id))) == ["published", "disabled"]
        candidate = conn.execute(select(tables["source_candidates"])).mappings().one()
        assert candidate["candidate_key"] == candidate_key_for(NEW + "/shop/S1", "16688")
        assert candidate["status"] == "rejected"
        assert conn.scalar(select(tables["ad_slots"].c.link_url).where(tables["ad_slots"].c.id == 1)) == NEW + "/?ref=kept"
        assert conn.scalar(select(tables["ad_slots"].c.link_url).where(tables["ad_slots"].c.id == 2)) == "https://www.16688.com.cn.evil.example/shop/S1"


def test_domain_identity_collision_aborts_all_changes(domain_db):
    engine, tables = domain_db
    with engine.begin() as conn:
        conn.execute(tables["source_intakes"].insert(), {"id": 3, "source_type": "16688", "source_url": NEW + "/shop/S1", "source_key": NEW + "/shop/S1", "status": "disabled"})
    with pytest.raises(ValueError, match="identity collision"):
        migration.migrate(engine, apply=True)
    with engine.connect() as conn:
        assert conn.scalar(select(tables["source_intakes"].c.source_url).where(tables["source_intakes"].c.id == 1)) == OLD + "/shop/S1"
        assert conn.scalar(select(tables["offers"].c.source_url)) == OLD + "/goods/G1"
