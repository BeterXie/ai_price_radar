import sqlite3
from datetime import datetime, timezone

from common import Base, CatalogSnapshot, Offer, Product, RawProduct, Shop
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import sync_ldxp


def test_load_records_opens_source_read_only(tmp_path, monkeypatch):
    source = tmp_path / "crawler.db"
    conn = sqlite3.connect(source)
    conn.executescript(
        """
        CREATE TABLE candidates (
            token TEXT PRIMARY KEY,
            status TEXT,
            source_score INTEGER,
            last_success_at TEXT,
            scanned_at TEXT
        );
        CREATE TABLE matches (
            token TEXT,
            product_name TEXT,
            collected_at TEXT
        );
        INSERT INTO candidates VALUES ('shop', 'success', 1, NULL, NULL);
        INSERT INTO matches VALUES ('shop', 'GPT Plus', '2026-07-26T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    original_connect = sqlite3.connect
    captured = {}

    def capture_connect(database, *args, **kwargs):
        captured["database"] = database
        captured["uri"] = kwargs.get("uri")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sync_ldxp.sqlite3, "connect", capture_connect)

    records = list(sync_ldxp.load_records(source))

    assert records[0]["product_name"] == "GPT Plus"
    assert captured["database"].endswith("?mode=ro")
    assert captured["uri"] is True


def test_load_records_preserves_intake_attempt_metadata(tmp_path):
    source = tmp_path / "crawler-with-intake.db"
    conn = sqlite3.connect(source)
    conn.executescript(
        """
        CREATE TABLE candidates (
            token TEXT PRIMARY KEY,
            status TEXT,
            source_score INTEGER,
            last_success_at TEXT,
            scanned_at TEXT,
            intake_id INTEGER,
            intake_attempt_count INTEGER
        );
        CREATE TABLE matches (
            token TEXT,
            product_name TEXT,
            product_url TEXT,
            collected_at TEXT
        );
        INSERT INTO candidates VALUES ('shop', 'success', 1000000, NULL, NULL, 9, 2);
        INSERT INTO matches VALUES ('shop', 'GPT Plus', 'https://example.test/item', '2026-07-26T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    records = list(sync_ldxp.load_records(source))
    assert records[0]["intake_id"] == 9
    assert records[0]["intake_attempt_count"] == 2


def test_onboard_only_after_published_import_succeeds():
    calls = []

    class FakeBridge:
        enabled = True

        def __init__(self, api_url, worker_key):
            assert api_url == "http://api"
            assert worker_key == "worker"

        def onboard(self, **payload):
            calls.append(payload)
            return {"status": "onboarded"}

    errors = sync_ldxp.onboard_published_intakes(
        {12: 3},
        {12: 4},
        api_url="http://api",
        worker_key="worker",
        bridge_factory=FakeBridge,
    )
    assert errors == []
    assert calls == [{"intake_id": 12, "attempt_count": 4, "product_count": 3}]

    errors = sync_ldxp.onboard_published_intakes(
        {12: 3},
        {12: 4},
        api_url="",
        worker_key="",
    )
    assert len(errors) == 1
    assert errors[0]["intake_id"] == 12
    assert "not configured" in errors[0]["error"]


def test_published_offer_counts_only_public_offers_in_current_snapshot():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        snapshot = CatalogSnapshot(source="ldxp", published_at=now)
        product = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        shop = Shop(token="ABC123", source_url="https://pay.ldxp.cn/shop/ABC123")
        db.add_all([snapshot, product, shop])
        db.flush()
        for index, values in enumerate((
            {"product_id": product.id, "active": True, "approved": True, "snapshot_id": snapshot.id},
            {"product_id": product.id, "active": True, "approved": False, "snapshot_id": snapshot.id},
            {"product_id": None, "active": True, "approved": True, "snapshot_id": snapshot.id},
            {"product_id": product.id, "active": True, "approved": True, "snapshot_id": snapshot.id - 1},
        )):
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=str(index),
                original_name=f"Product {index}",
            )
            db.add(raw)
            db.flush()
            db.add(Offer(raw_product_id=raw.id, shop_id=shop.id, **values))
        db.commit()
        counts = sync_ldxp.published_offer_counts(db, snapshot.id, {9: {"ABC123"}})
        assert counts == {9: 1}
        assert sync_ldxp.published_offer_counts(db, snapshot.id, {9: {"NO_PUBLIC"}}) == {}
