from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from common import (
    Base,
    CatalogSnapshot,
    Offer,
    RawProduct,
    Shop,
    ensure_products,
    session_for,
    utcnow,
)
from export_snapshot import export_public_snapshot


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    session = session_for(f"sqlite:///{db_path}")
    Base.metadata.create_all(session.get_bind())
    try:
        yield session
    finally:
        session.close()


def test_export_public_snapshot(db, tmp_path: Path):
    products = ensure_products(db)
    plus_product = products["chatgpt-plus"]

    shop = Shop(
        token="test-shop-1",
        name="测试小铺",
        source_url="https://example.com/shop",
        platform="ldxp",
        is_visible=True,
        status="success",
    )
    db.add(shop)
    db.commit()

    raw_prod = RawProduct(
        shop_id=shop.id,
        source_product_key="item-1",
        original_name="ChatGPT Plus 独享成品号",
        source_url="https://example.com/item/1",
    )
    db.add(raw_prod)
    db.commit()

    snapshot = CatalogSnapshot(source="test", offer_count=1, published_at=utcnow())
    db.add(snapshot)
    db.commit()

    offer = Offer(
        raw_product_id=raw_prod.id,
        product_id=plus_product.id,
        shop_id=shop.id,
        price=Decimal("120.00"),
        currency="CNY",
        stock_status="in_stock",
        stock_count=5,
        delivery_type="finished_account",
        is_comparable=True,
        service_period="one_month",
        warranty="first_login",
        snapshot_id=snapshot.id,
        active=True,
        approved=True,
    )
    db.add(offer)
    db.commit()

    output_dir = tmp_path / "data"
    result = export_public_snapshot(db, snapshot_id=snapshot.id, output_dir=output_dir)

    assert result["schema_version"] == "price-radar.v1"
    assert result["snapshot_id"] == str(snapshot.id)
    assert result["stale"] is False

    latest_file = output_dir / "latest.json"
    assert latest_file.is_file()
    latest_data = json.loads(latest_file.read_text(encoding="utf-8"))
    assert latest_data["snapshot_id"] == str(snapshot.id)

    snapshot_file = output_dir / "v1" / "snapshots" / f"{snapshot.id}.json"
    assert snapshot_file.is_file()
    snapshot_data = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert snapshot_data["product_count"] > 0

    plus_snap = next(p for p in snapshot_data["products"] if p["slug"] == "chatgpt-plus")
    assert plus_snap["min_price"] == 120.0
    assert plus_snap["offer_count"] == 1
    assert plus_snap["in_stock_count"] == 1
    assert len(plus_snap["top_5_offers"]) == 1
    assert plus_snap["top_5_offers"][0]["shop_token"] == "test-shop-1"
    assert plus_snap["top_5_offers"][0]["price"] == 120.0


def test_historical_export_never_rewrites_latest_pointer(db, tmp_path: Path):
    older = CatalogSnapshot(source="older", offer_count=0, published_at=utcnow())
    newer = CatalogSnapshot(source="newer", offer_count=0, published_at=utcnow())
    db.add_all([older, newer])
    db.commit()

    output_dir = tmp_path / "data"
    export_public_snapshot(db, snapshot_id=newer.id, output_dir=output_dir)
    before = (output_dir / "latest.json").read_text(encoding="utf-8")

    export_public_snapshot(
        db,
        snapshot_id=older.id,
        output_dir=output_dir,
        allow_historical=True,
    )

    assert (output_dir / "latest.json").read_text(encoding="utf-8") == before
    assert (output_dir / "v1" / "snapshots" / f"{older.id}.json").is_file()
