from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import Session

import publish_catalog
from app.database import Base as ApiBase
from app.models import Offer as ApiOffer
from common import Base, CatalogSnapshot, Offer, OfferHistory, begin_snapshot, ensure_products, upsert_offer, utcnow
from connectors import CONNECTORS
from offer_staging import StagedCatalogConflict, prepare_offer_staging
from publish_catalog import SourceSpec, publish_sources


def record(**changes):
    result = dict(token="stage-shop", shop_name="Stage Shop", shop_url="https://stage.example",
                  source_platform="woocommerce", product_key="one", product_name="ChatGPT Plus 月卡 独享",
                  product_url="https://stage.example/one", price="30.00", currency="CNY",
                  stock_count=5, stock_status="in_stock", observed_at=utcnow(), raw_json={})
    result.update(changes)
    return result


@pytest.fixture
def pg_engine(tmp_path, monkeypatch):
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required for real offer-row locking")
    schema = "offer_stage_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    ApiBase.metadata.create_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path / "feed"))
    import export_snapshot
    from app.services import notification_hub
    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "feed")
    monkeypatch.setattr(notification_hub, "dispatch_price_changes", lambda *args, **kwargs: [])
    try:
        yield engine
    finally:
        engine.dispose()
        assert schema.startswith("offer_stage_") and len(schema) == 44
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def seed(engine):
    with Session(engine, expire_on_commit=False) as db:
        products = ensure_products(db)
        snapshot = begin_snapshot(db, "seed")
        ids = set()
        upsert_offer(db, record(), products, snapshot.id, collected_offer_ids=ids)
        db.flush()
        offer_id = next(iter(ids))
        db.execute(update(Offer).where(Offer.id == offer_id).values(click_count=7))
        snapshot.published_at = utcnow()
        snapshot.offer_count = 1
        db.commit()
        return offer_id, snapshot.id


@pytest.mark.parametrize("carry_forward", [False, True])
def test_click_commits_while_publisher_replays_then_survives_merge(pg_engine, monkeypatch, carry_forward):
    offer_id, old_snapshot = seed(pg_engine)
    entered, release = Event(), Event()
    original = publish_catalog.upsert_offer
    monkeypatch.setitem(CONNECTORS, "stage-test", lambda _source: [record(price="31.00")])

    def paused(db, *args, **kwargs):
        result = original(db, *args, **kwargs)
        db.flush()
        entered.set()
        assert release.wait(10), "test release timeout"
        return result

    monkeypatch.setattr(publish_catalog, "upsert_offer", paused)

    def publish():
        with Session(pg_engine, expire_on_commit=False) as db:
            return publish_sources(db, [SourceSpec("stage-test", "stage")], carry_forward_current=carry_forward)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(publish)
        try:
            assert entered.wait(8), "publisher did not reach local replay"
            with Session(pg_engine) as click:
                click.execute(text("SET LOCAL lock_timeout='1000ms'"))
                # The API model also updates updated_at; it must not cause a staging conflict.
                count = click.scalar(update(ApiOffer).where(ApiOffer.id == offer_id)
                                     .values(click_count=ApiOffer.click_count + 1).returning(ApiOffer.click_count))
                click.commit()
                assert count == 8
        finally:
            release.set()
        result = future.result(timeout=10)
    with Session(pg_engine) as db:
        offer = db.get(Offer, offer_id)
        assert offer.click_count == 8
        assert offer.price == Decimal("31.00")
        assert offer.snapshot_id == result.snapshot_id != old_snapshot
        assert db.scalar(select(OfferHistory).where(OfferHistory.offer_id == offer_id).order_by(OfferHistory.id.desc())).price == Decimal("31.00")


def test_concurrent_manual_decision_aborts_merge_without_overwriting_it(pg_engine):
    offer_id, snapshot_id = seed(pg_engine)
    with Session(pg_engine) as publisher:
        staging = prepare_offer_staging(publisher)
        publisher.get(Offer, offer_id).price = Decimal("80.00")
        publisher.flush()
        with Session(pg_engine) as admin:
            admin.execute(update(ApiOffer).where(ApiOffer.id == offer_id).values(
                approved=False, tags=["manual_override"], classification_confidence=100))
            admin.commit()
        with pytest.raises(StagedCatalogConflict):
            staging.apply(publisher)
        publisher.rollback()
    with Session(pg_engine) as db:
        offer = db.get(Offer, offer_id)
        assert offer.approved is False and offer.tags == ["manual_override"]
        assert offer.classification_confidence == 100
        assert offer.price == Decimal("30.00") and offer.snapshot_id == snapshot_id


def test_new_offer_and_history_merge_with_real_foreign_keys(pg_engine):
    seed(pg_engine)
    with Session(pg_engine) as db:
        staging = prepare_offer_staging(db)
        products = ensure_products(db)
        snapshot = begin_snapshot(db, "new")
        ids = set()
        upsert_offer(db, record(product_key="two", product_url="https://stage.example/two"),
                     products, snapshot.id, collected_offer_ids=ids)
        db.flush()
        offer_id = next(iter(ids))
        staging.apply(db)
        db.commit()
        db.expire_all()
        assert db.get(Offer, offer_id).click_count == 0
        assert db.scalar(select(OfferHistory).where(OfferHistory.offer_id == offer_id)) is not None


def test_source_savepoint_rolls_back_staged_offer_and_history(pg_engine):
    offer_id, _ = seed(pg_engine)
    with Session(pg_engine) as db:
        staging = prepare_offer_staging(db)
        try:
            with db.begin_nested():
                db.get(Offer, offer_id).price = Decimal("999.00")
                db.add(OfferHistory(offer_id=offer_id, price=Decimal("999.00"), currency="CNY",
                                    stock_count=1, stock_status="in_stock", observed_at=utcnow()))
                db.flush()
                raise ValueError("source failed")
        except ValueError:
            pass
        staging.apply(db)
        db.commit()
    with Session(pg_engine) as db:
        assert db.get(Offer, offer_id).price == Decimal("30.00")
        assert not db.scalar(select(OfferHistory.id).where(OfferHistory.price == Decimal("999.00")))


@pytest.mark.parametrize("finish", ["commit", "rollback"])
def test_temp_tables_and_search_path_are_cleaned(pg_engine, finish):
    seed(pg_engine)
    with pg_engine.connect() as connection, Session(bind=connection) as db:
        original = db.scalar(text("SHOW search_path"))
        backend = db.scalar(text("SELECT pg_backend_pid()"))
        real_oid = db.scalar(text("SELECT 'offers'::regclass::oid"))
        staging = prepare_offer_staging(db)
        assert db.scalar(text("SELECT to_regclass('pg_temp.offers')")) is not None
        if finish == "commit":
            staging.apply(db)
            db.commit()
        else:
            db.rollback()
        assert db.scalar(text("SHOW search_path")) == original
        assert db.scalar(text("SELECT pg_backend_pid()")) == backend
        assert db.scalar(text("SELECT 'offers'::regclass::oid")) == real_oid
        for name in ["offers", "offer_history", "_catalog_offer_baseline"]:
            assert db.scalar(text("SELECT to_regclass(:name)"), {"name": "pg_temp." + name}) is None
