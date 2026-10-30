from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

import publish_catalog
from app.database import Base as ApiBase
from app.models import NotificationOutbox, Report, SourceIntake
from common import Base, CatalogSnapshot, Offer, Shop, utcnow
from connectors import CONNECTORS
from publish_catalog import SourceImportError, SourceSpec, approved_intake_sources, publish_sources


def goods(source: str, **overrides):
    value = dict(
        token=f"shop-{source}", shop_name=f"Shop {source}", shop_url=f"https://{source}.example",
        source_platform="woocommerce", product_key=f"goods-{source}",
        product_name="ChatGPT Plus 月卡 独享", product_url=f"https://{source}.example/product",
        listed_price="88.00", currency="CNY", stock_count=1, product_status="in_stock",
    )
    value.update(overrides)
    return value


@pytest.fixture(params=["sqlite", "postgres"])
def collection_db(request, monkeypatch, tmp_path):
    import export_snapshot

    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "feed")
    admin = None
    schema = None
    if request.param == "postgres":
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL is not configured")
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        schema = f"publish_collection_{uuid4().hex}"
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    try:
        Base.metadata.create_all(engine)
        ApiBase.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            yield db
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


@pytest.mark.parametrize("carry_forward", [False, True])
def test_all_sources_finish_collection_without_a_connection_or_publishing_writes(
    collection_db, monkeypatch, carry_forward,
):
    db = collection_db
    engine = db.get_bind()
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda source: iter([goods(str(source))]))
    previous = publish_sources(db, [SourceSpec("woocommerce-store", value) for value in ("a", "b")])
    # Simulate selection reads before publish_sources; they must also release their lease.
    target_id = db.scalar(select(Offer.id).join(Shop).where(Shop.token == "shop-a"))
    observations = []

    def check_while_collecting(source, stage):
        assert not db.in_transaction()
        assert engine.pool.checkedout() == 0
        with engine.begin() as connection:
            assert connection.scalar(select(CatalogSnapshot.id).where(
                CatalogSnapshot.published_at.is_not(None),
            ).order_by(CatalogSnapshot.id.desc()).limit(1)) == previous.snapshot_id
            # An independent writer must still update the old Offer after a yielded
            # record and even while the later source is being collected.
            connection.execute(text("UPDATE offers SET click_count=click_count+1 WHERE id=:id"), {"id": target_id})
        observations.append((source, stage))

    def collecting_loader(source):
        check_while_collecting(source, "before")
        yield goods(str(source), listed_price="99.00")
        check_while_collecting(source, "after")

    monkeypatch.setitem(CONNECTORS, "woocommerce-store", collecting_loader)
    result = publish_sources(db, [SourceSpec("woocommerce-store", value) for value in ("a", "b")],
                             carry_forward_current=carry_forward)
    assert observations == [("a", "before"), ("a", "after"), ("b", "before"), ("b", "after")]
    db.expire_all()
    assert db.get(Offer, target_id).click_count == 4
    assert result.offer_count == 2
    assert db.query(CatalogSnapshot).count() == 2


def test_database_validation_failure_rolls_back_the_whole_replay(collection_db, monkeypatch):
    db = collection_db
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda source: iter([goods(str(source))]))
    previous = publish_sources(db, [SourceSpec("woocommerce-store", "a")])

    def invalid_loader(source):
        if source == "a":
            yield goods("a", listed_price="99.00")
        else:
            yield goods("b", raw_json=[])

    monkeypatch.setitem(CONNECTORS, "woocommerce-store", invalid_loader)
    with pytest.raises(SourceImportError, match="raw_json must be a JSON object"):
        publish_sources(db, [SourceSpec("woocommerce-store", value) for value in ("a", "b")])
    db.expire_all()
    assert db.query(CatalogSnapshot).count() == 1
    assert db.query(Offer).one().snapshot_id == previous.snapshot_id
    assert db.query(Offer).one().price == Decimal("88.00")
    assert db.query(Shop).count() == 1


def test_typed_connector_fields_round_trip_through_spool(collection_db, monkeypatch):
    observed = utcnow() - timedelta(hours=2)
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda _source: iter([
        goods("a", listed_price=Decimal("91.23"), observed_at=observed),
    ]))
    publish_sources(collection_db, [SourceSpec("woocommerce-store", "a")])
    offer = collection_db.query(Offer).one()
    assert offer.price == Decimal("91.23")
    assert offer.observed_at.replace(tzinfo=None) == observed.replace(tzinfo=None)


@pytest.mark.parametrize("carry_forward", [False, True])
@pytest.mark.parametrize("collection_outcome", ["records", "empty", "fetch_failed"])
def test_intake_revocation_during_collection_is_rechecked_before_replay(
    collection_db, monkeypatch, carry_forward, collection_outcome,
):
    from connectors.base import SourceFetchError

    db = collection_db
    intake = SourceIntake(source_type="woocommerce", detected_platform="woocommerce",
                          source_key="https://a.example", source_url="https://a.example", status="approved",
                          contact_email="collection@example.invalid")
    db.add(intake)
    db.commit()
    intake_id = intake.id
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda _source: iter([goods("a")]))
    previous = publish_sources(db, approved_intake_sources(db))
    sources = approved_intake_sources(db)

    def revoked_loader(_source):
        assert not db.in_transaction()
        with db.get_bind().begin() as connection:
            connection.execute(text("UPDATE source_intakes SET status='disabled' WHERE id=:id"), {"id": intake_id})
        if collection_outcome == "empty":
            return
        if collection_outcome == "fetch_failed":
            raise SourceFetchError("upstream timeout")
        yield goods("a", listed_price="99.00")

    monkeypatch.setitem(CONNECTORS, "woocommerce-store", revoked_loader)
    result = publish_sources(db, sources, carry_forward_current=carry_forward)
    assert [item.status for item in result.imports] == ["skipped_inactive"]
    assert result.offer_count == 0
    db.expire_all()
    assert db.get(SourceIntake, intake_id).status == "disabled"
    assert db.query(Offer).one().price == Decimal("88.00")
    assert db.query(Offer).one().snapshot_id == previous.snapshot_id


def test_newer_publication_during_collection_is_not_overwritten(collection_db, monkeypatch):
    db = collection_db
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda source: iter([goods(str(source))]))
    previous = publish_sources(db, [SourceSpec("woocommerce-store", "a")])
    newer_ids = []

    def newer_publish(_source):
        assert not db.in_transaction()
        with Session(db.get_bind()) as other:
            snapshot = CatalogSnapshot(source="other-publisher", published_at=utcnow(), offer_count=0)
            other.add(snapshot)
            other.commit()
            newer_ids.append(snapshot.id)
        yield goods("b")

    monkeypatch.setitem(CONNECTORS, "woocommerce-store", newer_publish)
    with pytest.raises(SourceImportError, match="catalog changed during source collection"):
        publish_sources(db, [SourceSpec("woocommerce-store", "b")])
    assert db.query(CatalogSnapshot).count() == 2
    assert db.query(CatalogSnapshot).order_by(CatalogSnapshot.id.desc()).first().id == newer_ids[0]
    assert db.query(Offer).one().snapshot_id == previous.snapshot_id


@pytest.mark.parametrize("exceed_limit", [False, True])
def test_spool_is_cleaned_on_success_and_collection_failure(collection_db, monkeypatch, tmp_path, exceed_limit):
    actual_temporary_directory = publish_catalog.tempfile.TemporaryDirectory
    paths = []

    def tracked_directory(**kwargs):
        value = actual_temporary_directory(dir=tmp_path, **kwargs)
        paths.append(Path(value.name))
        return value

    monkeypatch.setattr(publish_catalog.tempfile, "TemporaryDirectory", tracked_directory)
    monkeypatch.setitem(CONNECTORS, "woocommerce-store", lambda _source: iter([goods("a")]))
    if exceed_limit:
        monkeypatch.setattr(publish_catalog, "MAX_PREPARED_CATALOG_BYTES", 16)
        with pytest.raises(SourceImportError, match="collection limit"):
            publish_sources(collection_db, [SourceSpec("woocommerce-store", "a")])
        assert collection_db.query(CatalogSnapshot).count() == 0
    else:
        publish_sources(collection_db, [SourceSpec("woocommerce-store", "a")])
    assert paths and all(not path.exists() for path in paths)


def test_uncommitted_objects_are_preserved_instead_of_discarded(collection_db):
    pending = Shop(token="pending", name="Pending", source_url="https://pending.example")
    collection_db.add(pending)
    with pytest.raises(ValueError, match="commit pending changes"):
        publish_sources(collection_db, [SourceSpec("woocommerce-store", "a")])
    assert pending in collection_db.new
