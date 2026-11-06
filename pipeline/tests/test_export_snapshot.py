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


@pytest.mark.parametrize("source_platform", ["ldxp", "dujiao_next"])
def test_export_public_snapshot(db, tmp_path: Path, source_platform):
    products = ensure_products(db)
    plus_product = products["chatgpt-plus"]
    plus_product.search_keywords = ["OpenAI", "subscription"]

    shop = Shop(
        token="test-shop-1",
        name="测试小铺",
        source_url="https://example.com/shop",
        platform=source_platform,
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
        click_count=17,
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
    assert snapshot_data["search_schema_version"] == 1
    assert snapshot_data["stale_offer_hours"] == 72
    assert plus_snap["offers"][0]["account_access"] == "exclusive"
    assert "plus" in plus_snap["search_aliases"]
    assert "OpenAI" not in plus_snap["search_aliases"]
    assert plus_snap["search_keywords"] == ["OpenAI", "subscription"]
    assert plus_snap["offers"][0]["observed_at"]
    assert plus_snap["offers"][0]["click_count"] == 17


def test_export_contains_every_public_quote_and_filters_hidden_stale_rows(db, tmp_path, monkeypatch):
    from datetime import timedelta
    products = ensure_products(db)
    shop = Shop(token="all-quotes", name="报价店", source_url="https://example.com")
    snapshot = CatalogSnapshot(source="test", published_at=utcnow())
    db.add_all([shop, snapshot])
    db.flush()
    for index in range(12):
        raw = RawProduct(shop_id=shop.id, source_product_key=str(index), original_name=f"Plus 月付 {'独享' if index == 6 else '成品号'}")
        db.add(raw)
        db.flush()
        db.add(Offer(
            raw_product_id=raw.id, product_id=products["chatgpt-plus"].id, shop_id=shop.id,
            snapshot_id=snapshot.id, price=Decimal(100 + index), stock_status="in_stock",
            delivery_type="finished_account", service_period="one_month", is_comparable=True,
            active=index != 7, approved=index != 8, hidden_reason="hidden" if index == 9 else "",
            observed_at=utcnow() - timedelta(hours=80 if index == 10 else 0),
        ))
    products["claude-pro"].is_visible = False
    db.commit()
    export_public_snapshot(db, output_dir=tmp_path)
    data = json.loads((tmp_path / "v1" / "snapshots" / f"{snapshot.id}.json").read_text(encoding="utf-8"))
    plus = next(p for p in data["products"] if p["slug"] == "chatgpt-plus")
    assert len(plus["offers"]) == plus["offer_count"] == 8
    assert len(plus["top_5_offers"]) == 5
    assert any(o["price"] == 106 and o["account_access"] == "exclusive" for o in plus["offers"])
    assert all(o["account_access"] == "unknown" for o in plus["offers"] if o["price"] != 106)
    assert not any(p["slug"] == "claude-pro" for p in data["products"])
    assert data["offer_count"] == sum(len(p["offers"]) for p in data["products"])
    # Exercise the actual published file through the bot, with the database closed.
    db.close()
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path))
    from extensions.bots.chat_commands import handle_chat_command
    reply = handle_chat_command("plus 独享 月付 110元以内", sender_id="snapshot-e2e")
    assert "¥106.00" in reply and "¥100.00" not in reply


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
