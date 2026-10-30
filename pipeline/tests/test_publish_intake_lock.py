from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

import publish_catalog
from app.database import Base as ApiBase
from app.models import SourceIntake
from common import Base, CatalogSnapshot, Offer, utcnow
from connectors import CONNECTORS
from publish_catalog import SourceSpec, approved_intake_sources, publish_sources


@pytest.fixture
def intake_lock_engine(monkeypatch):
    """Use only TEST_POSTGRES_URL and isolate every table in a disposable schema."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    schema = f"publish_intake_lock_{uuid4().hex}"
    schema_admin = create_engine(url)
    engine = None
    created = False
    try:
        with schema_admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(
            url,
            connect_args={
                "options": (
                    f"-csearch_path={schema} "
                    "-cstatement_timeout=20000 -clock_timeout=10000"
                ),
            },
            pool_size=4,
            max_overflow=0,
            pool_timeout=5,
        )
        Base.metadata.create_all(engine)
        ApiBase.metadata.create_all(engine)
        # Feed output is unrelated to row locking; keep this test entirely in its schema.
        import export_snapshot

        monkeypatch.setattr(export_snapshot, "export_public_snapshot", lambda *_args, **_kwargs: None)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with schema_admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        schema_admin.dispose()


@pytest.mark.parametrize("source_kind", ["intake_id", "legacy_dujiao_origin"])
def test_approval_change_waits_for_publication_then_remains_disabled(
    intake_lock_engine, monkeypatch, source_kind,
):
    """An admin cannot revoke an intake between publication recheck and commit.

    Pause after the first replayed upsert, before the publisher's normal intake
    status UPDATE. Only the explicit approval row lock can serialize the admin
    at this point; the earlier implementation's SELECT checks let it commit.
    """
    engine = intake_lock_engine
    origin = "https://intake-lock.example"
    legacy = source_kind == "legacy_dujiao_origin"
    connector = "dujiao-next" if legacy else "woocommerce-store"
    platform = "dujiao_next" if legacy else "woocommerce"
    observed_at = utcnow().isoformat()

    def loader(_source):
        yield {
            "token": "shop-intake-lock",
            "shop_name": "Intake lock shop",
            "shop_url": origin,
            "source_platform": platform,
            "product_key": "intake-lock-plus",
            "product_name": "ChatGPT Plus 月卡 独享",
            "product_url": f"{origin}/product/plus",
            "listed_price": "88.00",
            "currency": "CNY",
            "stock_count": 1,
            "product_status": "in_stock",
            "observed_at": observed_at,
        }

    monkeypatch.setitem(CONNECTORS, connector, loader)
    with Session(engine, expire_on_commit=False) as setup:
        intake = SourceIntake(
            source_type=platform,
            detected_platform=platform,
            source_key=origin,
            source_url=origin,
            contact_email="intake-lock@example.invalid",
            status="approved",
            approved_at=utcnow() - timedelta(days=1),
        )
        setup.add(intake)
        setup.commit()
        intake_id = intake.id
        sources = (
            [SourceSpec(connector, origin)]
            if legacy else approved_intake_sources(setup)
        )
        assert len(sources) == 1
        assert sources[0].intake_ids == (() if legacy else (intake_id,))
        previous = publish_sources(setup, sources)
        previous_snapshot_id = previous.snapshot_id
        assert previous.offer_count == 1
        baseline_status = setup.scalar(
            select(SourceIntake.status).where(SourceIntake.id == intake_id),
        )

    replay_started = Event()
    release_replay = Event()
    admin_started = Event()
    admin_finished = Event()
    backend_pids = {}
    original_upsert = publish_catalog.upsert_offer

    def paused_upsert(db, *args, **kwargs):
        result = original_upsert(db, *args, **kwargs)
        if not replay_started.is_set():
            backend_pids["publisher"] = db.scalar(text("SELECT pg_backend_pid()"))
            replay_started.set()
            if not release_replay.wait(15):
                raise AssertionError("publisher replay was not released by the test")
        return result

    monkeypatch.setattr(publish_catalog, "upsert_offer", paused_upsert)

    def run_publisher():
        # Each thread owns its Session and connection; no shared-session shortcuts.
        with Session(engine, expire_on_commit=False) as db:
            return publish_sources(db, sources, carry_forward_current=True)

    def disable_intake():
        try:
            with engine.begin() as connection:
                backend_pids["admin"] = connection.scalar(text("SELECT pg_backend_pid()"))
                admin_started.set()
                changed = connection.execute(
                    text("UPDATE source_intakes SET status='disabled' WHERE id=:id"),
                    {"id": intake_id},
                ).rowcount
                # Read after the UPDATE actually acquired its lock. Under READ COMMITTED
                # it must now observe the publisher's committed snapshot.
                visible_snapshot_id = connection.scalar(
                    select(CatalogSnapshot.id)
                    .where(CatalogSnapshot.published_at.is_not(None))
                    .order_by(CatalogSnapshot.id.desc())
                    .limit(1),
                )
            return changed, visible_snapshot_id
        finally:
            admin_finished.set()

    with ThreadPoolExecutor(max_workers=2) as workers:
        publisher_future = workers.submit(run_publisher)
        admin_future = None
        try:
            assert replay_started.wait(10), "publisher never reached the replay barrier"
            admin_future = workers.submit(disable_intake)
            assert admin_started.wait(5), "admin never acquired an independent connection"
            assert backend_pids["publisher"] != backend_pids["admin"]

            blockers = []
            deadline = time.monotonic() + 5
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                while time.monotonic() < deadline:
                    blockers = observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": backend_pids["admin"]},
                    )
                    if backend_pids["publisher"] in blockers or admin_finished.is_set():
                        break
                    admin_finished.wait(0.02)
                assert backend_pids["publisher"] in blockers, (
                    "admin UPDATE must wait on the publisher before replay finishes; "
                    f"blockers={blockers}, admin_finished={admin_finished.is_set()}"
                )
                assert not admin_finished.is_set()
                assert observer.scalar(
                    text("SELECT status FROM source_intakes WHERE id=:id"),
                    {"id": intake_id},
                ) == baseline_status
        finally:
            # Release on assertions as well, so a failing old implementation cannot
            # strand a worker or leave schema locks behind during fixture teardown.
            release_replay.set()
            try:
                result = publisher_future.result(timeout=20)
            finally:
                if admin_future is not None:
                    changed, admin_visible_snapshot_id = admin_future.result(timeout=20)

    assert changed == 1
    assert result.snapshot_id != previous_snapshot_id
    assert result.offer_count == 1
    assert admin_visible_snapshot_id == result.snapshot_id
    with Session(engine) as check:
        assert check.scalar(
            select(SourceIntake.status).where(SourceIntake.id == intake_id),
        ) == "disabled"
        assert check.scalar(
            select(CatalogSnapshot.id)
            .where(CatalogSnapshot.published_at.is_not(None))
            .order_by(CatalogSnapshot.id.desc())
            .limit(1),
        ) == result.snapshot_id
        assert check.scalar(select(Offer.snapshot_id)) == result.snapshot_id
