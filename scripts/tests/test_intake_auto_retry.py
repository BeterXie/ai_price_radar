from __future__ import annotations

import os
import sqlite3
import sys
from datetime import timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "pipeline"))

import publish_catalog
from app.database import Base as ApiBase
from app.models import NotificationOutbox, Report, SourceIntake
from common import Base, CatalogSnapshot, Offer, utcnow
from connectors import CONNECTORS
from publish_catalog import (
    SourceImportError,
    SourceSpec,
    approved_dujiao_sources,
    approved_intake_sources,
    merge_sources,
    publish_sources,
)


@pytest.fixture(params=["sqlite", "postgres"])
def retry_db(request, monkeypatch, tmp_path):
    """Exercise real approval/timestamp columns; PostgreSQL uses a disposable schema."""
    import export_snapshot

    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "feed")
    admin_engine = None
    schema = None
    if request.param == "postgres":
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL is not configured")
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        schema = f"intake_retry_{uuid4().hex}"
        admin_engine = create_engine(url)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        ApiBase.metadata.create_all(engine, tables=[
            Report.__table__, SourceIntake.__table__, NotificationOutbox.__table__,
        ])
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()
        if admin_engine is not None:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()


@pytest.fixture
def clock(monkeypatch):
    # An exact second also covers SQLite's datetime serialization at the boundary.
    value = [utcnow().replace(microsecond=0)]
    monkeypatch.setattr(publish_catalog, "utcnow", lambda: value[0])
    return value


def add_intake(db, now, *, source_type="16688", **overrides):
    url = "https://www.16688.com.cn/shop/S878919" if source_type == "16688" else "https://retry.example"
    values = dict(
        source_type=source_type, detected_platform=source_type, source_key=url,
        source_url=url, shop_name="Retry shop", contact_email="retry@example.invalid",
        status="approved", approved_at=now - timedelta(days=1), updated_at=now,
    )
    values.update(overrides)
    intake = SourceIntake(**values)
    db.add(intake)
    db.commit()
    return intake


def goods(now, key="PLUS", title="ios正规plus年卡全程质保", *, platform="16688"):
    return dict(
        token="16688-S878919" if platform == "16688" else "retry-shop",
        shop_name="Retry shop",
        shop_url="https://www.16688.com.cn/shop/S878919" if platform == "16688" else "https://retry.example",
        source_platform=platform, product_key=key, product_name=title,
        product_url=f"https://www.16688.com.cn/goods/{key}", listed_price="135",
        currency="CNY", stock_count=1, product_status="in_stock", collected_at=now.isoformat(),
    )


def notification_counts(db):
    return dict(db.execute(text(
        "SELECT event_type, count(*) FROM notification_outbox GROUP BY event_type"
    )).all())


def test_16688_empty_catalog_retries_after_cooldown_then_recovers_without_duplicate_notifications(
    retry_db, clock, monkeypatch,
):
    db = retry_db
    intake = add_intake(db, clock[0])
    titles = [("PLUS", "ios正规plus年卡全程质保")]
    calls = []

    def loader(source):
        calls.append(str(source))
        for key, title in titles:
            yield goods(clock[0], key, title)

    monkeypatch.setitem(CONNECTORS, "16688", loader)
    first = publish_sources(db, approved_intake_sources(db))
    db.refresh(intake)
    assert (first.imports[0].raw_record_count, first.imports[0].public_offer_count) == (1, 0)
    assert (intake.status, intake.product_count) == ("no_products", 0)
    assert intake.finished_at.replace(tzinfo=timezone.utc) == clock[0]
    assert notification_counts(db) == {"shop_intake.no_products": 1}

    for _ in range(2):
        assert approved_intake_sources(db) == []
    clock[0] += timedelta(hours=1) - timedelta(microseconds=1)
    assert approved_intake_sources(db) == []
    assert len(calls) == 1

    # Another completed read still has no eligible product; it restarts the cooldown.
    clock[0] += timedelta(microseconds=1)
    second = publish_sources(db, approved_intake_sources(db))
    db.refresh(intake)
    assert second.imports[0].public_offer_count == 0
    assert intake.status == "no_products"
    assert intake.finished_at.replace(tzinfo=timezone.utc) == clock[0]
    assert approved_intake_sources(db) == []
    assert notification_counts(db) == {"shop_intake.no_products": 1}

    titles.extend([
        ("PRO5", "【美区IOS】质保30天 G pro5x 订阅 官方充值"),
        ("PRO20", "【美区IOS】质保30天 G pro 20x 订阅 官方充值"),
    ])
    clock[0] += timedelta(hours=1)
    recovered = publish_sources(db, approved_intake_sources(db))
    db.refresh(intake)
    imported = recovered.imports[0]
    assert (imported.raw_record_count, imported.classified_offer_count, imported.public_offer_count) == (3, 2, 2)
    assert (intake.status, intake.product_count) == ("published", 2)
    assert intake.finished_at.replace(tzinfo=timezone.utc) == clock[0]
    assert db.scalar(select(Offer).where(Offer.product_id.is_(None))).approved is False
    assert notification_counts(db) == {"shop_intake.no_products": 1, "shop_intake.onboarded": 1}

    # Published shops continue normal sync, without a retry cooldown or repeated mail.
    publish_sources(db, approved_intake_sources(db))
    assert len(calls) == 4
    assert notification_counts(db) == {"shop_intake.no_products": 1, "shop_intake.onboarded": 1}


def test_retry_cooldown_starts_when_the_source_read_finishes(retry_db, clock, monkeypatch):
    db = retry_db
    started_at = clock[0]
    intake = add_intake(db, started_at)

    def slow_loader(_source):
        clock[0] += timedelta(minutes=20)
        yield goods(clock[0])

    monkeypatch.setitem(CONNECTORS, "16688", slow_loader)
    publish_sources(db, approved_intake_sources(db))
    db.refresh(intake)
    assert intake.finished_at.replace(tzinfo=timezone.utc) == started_at + timedelta(minutes=20)
    assert approved_intake_sources(db, now=started_at + timedelta(hours=1)) == []
    assert approved_intake_sources(db, now=started_at + timedelta(hours=1, minutes=20)) == [
        SourceSpec("16688", intake.source_url, (intake.id,)),
    ]


@pytest.mark.parametrize(("source_type", "connector"), [
    ("16688", "16688"), ("dujiao_next", "dujiao-next"),
    ("merchant_json", "merchant-json"), ("woocommerce", "woocommerce-store"),
    ("schema_org", "schema-org"), ("acg_faka", "acg-faka"),
])
def test_retry_selects_only_approved_verified_supported_sources(retry_db, clock, source_type, connector):
    intake = add_intake(
        retry_db, clock[0], source_type=source_type, status="no_products",
        finished_at=clock[0] - timedelta(hours=1),
    )
    assert approved_intake_sources(retry_db) == [SourceSpec(connector, intake.source_url, (intake.id,))]


@pytest.mark.parametrize("source_type", ["16688", "dujiao_next"])
@pytest.mark.parametrize("overrides", [
    {"approved_at": None}, {"detected_platform": "other"},
    {"status": "rejected"}, {"status": "disabled"}, {"status": "needs_re_review"},
    {"status": "pending_review"}, {"status": "validation_failed"},
])
def test_retry_excludes_unapproved_mismatched_and_manual_decisions(
    retry_db, clock, monkeypatch, source_type, overrides,
):
    intake = add_intake(
        retry_db, clock[0], source_type=source_type,
        **{"status": "no_products", "finished_at": clock[0] - timedelta(days=2), **overrides},
    )
    assert approved_intake_sources(retry_db) == []
    if source_type == "dujiao_next":
        def forbidden_loader(_source):
            pytest.fail("legacy approval must not bypass the current intake decision")
        monkeypatch.setitem(CONNECTORS, "dujiao-next", forbidden_loader)
        result = publish_sources(retry_db, [SourceSpec("dujiao-next", intake.source_url)])
        assert [item.status for item in result.imports] == ["skipped_inactive"]
        assert result.offer_count == 0


@pytest.mark.parametrize("has_finished_at", [False, True])
def test_retry_uses_completion_time_then_updated_time_for_legacy_rows(retry_db, clock, has_finished_at):
    cutoff = clock[0] - timedelta(hours=1)
    intake = add_intake(
        retry_db, clock[0], status="no_products",
        finished_at=cutoff if has_finished_at else None,
        updated_at=clock[0] if has_finished_at else cutoff,
    )
    assert approved_intake_sources(retry_db) == [SourceSpec("16688", intake.source_url, (intake.id,))]


def test_legacy_dujiao_approval_obeys_cooldown_and_allows_due_retry(retry_db, clock, tmp_path, monkeypatch):
    db = retry_db
    intake = add_intake(db, clock[0], source_type="dujiao_next", status="no_products", finished_at=clock[0])
    review_db = tmp_path / "review.db"
    with sqlite3.connect(review_db) as review:
        review.execute("CREATE TABLE dujiao_candidates (origin TEXT, api_verified INT, status TEXT, review_status TEXT)")
        review.execute("INSERT INTO dujiao_candidates VALUES (?, 1, 'verified', 'approved')", (intake.source_url,))
    legacy = [SourceSpec("dujiao-next", source) for source in approved_dujiao_sources(review_db)]
    calls = []

    def loader(source):
        calls.append(str(source))
        yield goods(clock[0], "PRO5", "ChatGPT Pro 5x 直充", platform="dujiao_next")

    monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
    clock[0] += timedelta(minutes=59)
    selection_time = clock[0]
    assert approved_intake_sources(db, now=selection_time) == []
    # The clock can cross the boundary between source selection and execution.
    clock[0] += timedelta(minutes=1)
    skipped = publish_sources(db, legacy, now=selection_time)
    assert [item.status for item in skipped.imports] == ["skipped_inactive"]
    assert calls == []

    selection_time = clock[0]
    sources = merge_sources([*legacy, *approved_intake_sources(db, now=selection_time)])
    result = publish_sources(db, sources, now=selection_time)
    assert calls == [intake.source_url]
    assert result.imports[0].public_offer_count == 1
    db.refresh(intake)
    assert (intake.status, intake.product_count) == ("published", 1)


@pytest.mark.parametrize("decision", ["rejected", "disabled", "needs_re_review"])
def test_retry_result_does_not_overwrite_manual_decision_or_send_onboarded_mail(
    retry_db, clock, monkeypatch, decision,
):
    db = retry_db
    intake = add_intake(db, clock[0], status="no_products", finished_at=clock[0] - timedelta(hours=2))
    sources = approved_intake_sources(db)
    previous_finished_at = intake.finished_at

    def loader(_source):
        # Reproduce a decision made after scheduling and before result persistence.
        db.execute(text("UPDATE source_intakes SET status=:status WHERE id=:id"), {"status": decision, "id": intake.id})
        yield goods(clock[0], "PRO5", "G pro5x 官方充值")

    monkeypatch.setitem(CONNECTORS, "16688", loader)
    publish_sources(db, sources)
    db.refresh(intake)
    assert intake.status == decision
    assert intake.finished_at == previous_finished_at
    assert notification_counts(db) == {}


def test_failed_atomic_publication_leaves_retry_due(retry_db, clock, monkeypatch):
    db = retry_db
    intake = add_intake(db, clock[0], status="no_products", finished_at=clock[0] - timedelta(hours=2))
    previous_finished_at = intake.finished_at
    sources = approved_intake_sources(db)
    monkeypatch.setitem(CONNECTORS, "16688", lambda _source: iter([goods(clock[0], "PRO5", "G pro5x 官方充值")]))

    def broken_loader(_source):
        raise ValueError("malformed catalog")

    monkeypatch.setitem(CONNECTORS, "merchant-json", broken_loader)
    with pytest.raises(SourceImportError, match="malformed catalog"):
        publish_sources(db, [*sources, SourceSpec("merchant-json", "broken")])
    db.refresh(intake)
    assert (intake.status, intake.product_count, intake.finished_at) == ("no_products", 0, previous_finished_at)
    assert approved_intake_sources(db) == sources
    assert notification_counts(db) == {}
    assert db.query(CatalogSnapshot).count() == 0
