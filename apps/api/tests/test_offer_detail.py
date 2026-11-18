from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop
from app.services.catalog import get_current_snapshot


@pytest.fixture
def catalog():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        snapshot = CatalogSnapshot(published_at=datetime.now(timezone.utc))
        product = Product(slug="chatgpt-business", platform="OpenAI", display_name="ChatGPT Business")
        shop = Shop(token="exact-shop", name="提醒中的商家", source_url="https://merchant.example")
        db.add_all([snapshot, product, shop])
        db.flush()
        offers = []
        for index, price in enumerate(("10.00", "20.00")):
            raw = RawProduct(
                shop_id=shop.id, source_product_key=f"item-{index}", original_name="Team 5x 同名商品",
                raw_json={"description": f"<p>第 {index} 件商品</p><script>secret()</script>"},
            )
            db.add(raw)
            db.flush()
            offer = Offer(
                raw_product_id=raw.id, product_id=product.id, shop_id=shop.id, snapshot_id=snapshot.id,
                price=Decimal(price), currency="CNY", stock_status="in_stock", stock_count=3,
                is_comparable=False, source_url=f"https://merchant.example/items/{index}",
            )
            db.add(offer)
            offers.append(offer)
        db.commit()
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                yield db, client, offers[1]
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


def test_offer_link_returns_exact_sku_even_with_identical_titles(catalog):
    db, client, offer = catalog
    response = client.get(f"/api/v1/offers/{offer.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == offer.id
    assert data["price"] == "20.00"
    assert data["shop_name"] == "提醒中的商家"
    assert data["source_url"] == "https://merchant.example/items/1"
    assert data["product_slug"] == "chatgpt-business"
    assert data["original_description"] == "第 1 件商品"
    assert data["is_comparable"] is False


def test_offer_link_reads_new_price_and_stock_after_snapshot_refresh(catalog):
    db, client, offer = catalog
    previous = get_current_snapshot(db)
    newer = CatalogSnapshot(published_at=datetime.now(timezone.utc))
    db.add(newer)
    db.flush()
    offer.snapshot_id = newer.id
    offer.price = Decimal("21.00")
    offer.stock_status = "out_of_stock"
    offer.stock_count = 0
    db.commit()
    assert previous.id != newer.id
    response = client.get(f"/api/v1/offers/{offer.id}")
    assert response.status_code == 200
    assert response.json()["price"] == "21.00"
    assert response.json()["stock_status"] == "out_of_stock"


@pytest.mark.parametrize("hidden", ["inactive", "unapproved", "hidden_reason", "shop", "closed_shop", "product", "expired", "old_snapshot"])
def test_nonpublic_offer_ids_do_not_expose_seller_details(catalog, hidden):
    db, client, offer = catalog
    if hidden == "inactive":
        offer.active = False
    elif hidden == "unapproved":
        offer.approved = False
    elif hidden == "hidden_reason":
        offer.hidden_reason = "审核隐藏"
    elif hidden == "shop":
        offer.shop.is_visible = False
    elif hidden == "closed_shop":
        offer.shop.status = "closed"
    elif hidden == "product":
        offer.product.is_visible = False
    elif hidden == "expired":
        offer.observed_at = datetime.now(timezone.utc) - timedelta(hours=get_settings().stale_offer_hours + 1)
    else:
        db.add(CatalogSnapshot(published_at=datetime.now(timezone.utc)))
    db.commit()
    response = client.get(f"/api/v1/offers/{offer.id}")
    assert response.status_code == 404
    assert "merchant.example" not in response.text


def test_nonexistent_offer_link_returns_404(catalog):
    _, client, _ = catalog
    assert client.get("/api/v1/offers/999999").status_code == 404
    assert client.get(f"/api/v1/offers/{2**70}").status_code == 404


def test_price_warning_uses_public_comparable_peers_and_excludes_closed_shops(catalog):
    db, client, offer = catalog
    offer.is_comparable = True
    peer_shop = Shop(token="median-peer", name="对照商家", source_url="https://peer.example", status="normal")
    db.add(peer_shop)
    db.flush()
    for index in range(2):
        raw = RawProduct(shop_id=peer_shop.id, source_product_key=str(index), original_name="Team 对照报价")
        db.add(raw)
        db.flush()
        db.add(Offer(
            raw_product_id=raw.id, product_id=offer.product_id, shop_id=peer_shop.id,
            snapshot_id=offer.snapshot_id, price=Decimal("1000"), currency=offer.currency,
            delivery_type=offer.delivery_type, stock_status="in_stock", is_comparable=True,
        ))
    db.commit()
    data = client.get(f"/api/v1/offers/{offer.id}").json()
    assert data["is_trusted_price"] is False
    assert data["low_price_warning"]
    peer_shop.status = "closed"
    db.commit()
    data = client.get(f"/api/v1/offers/{offer.id}").json()
    assert data["is_trusted_price"] is True
    assert data["low_price_warning"] is None
