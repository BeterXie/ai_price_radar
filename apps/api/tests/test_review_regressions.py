from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, OfferHistory, Product, RawProduct, Shop


@pytest.fixture
def catalog_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(get_settings(), "admin_api_key", "admin-test")
    with Session(engine) as db:
        snapshot = CatalogSnapshot(source="test", published_at=datetime.now(timezone.utc))
        product = Product(slug="review-product", platform="OpenAI", display_name="Review product")
        shop = Shop(token="review-shop", name="Review shop", source_url="https://example.com")
        db.add_all([snapshot, product, shop])
        db.flush()
        raw = RawProduct(shop_id=shop.id, source_product_key="first", original_name="Keep offer", raw_json={"description": "Public description"})
        db.add(raw)
        db.flush()
        offer = Offer(
            raw_product_id=raw.id, shop_id=shop.id, product_id=product.id, snapshot_id=snapshot.id,
            price=Decimal("10"), stock_status="in_stock", delivery_type="finished_account",
            is_comparable=True, item_fingerprint="same", source_url=shop.source_url,
        )
        db.add(offer)
        db.flush()
        db.add(OfferHistory(offer_id=offer.id, price=offer.price, stock_status="in_stock"))
        db.commit()
        ids = snapshot.id, product.id, shop.id, offer.id

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), engine, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_unpublished_snapshot_never_exposes_offers(catalog_client):
    client, engine, (snapshot_id, _, _, offer_id) = catalog_client
    with Session(engine) as db:
        db.get(CatalogSnapshot, snapshot_id).published_at = None
        db.commit()
    assert client.get("/api/v1/products").json()["items"] == []
    assert client.get("/api/v1/catalog/groups").json()["items"] == []
    assert client.get("/api/v1/shops").json() == []
    assert client.get("/api/v1/shops/cards").json()["total"] == 0
    assert client.get("/api/v1/meta").json()["source_platforms"] == []
    assert client.get(f"/api/v1/offers/{offer_id}/description").status_code == 404
    assert client.get("/api/v1/products/review-product/history").json()["trend"] == []


@pytest.mark.parametrize("hidden_scope", ["product", "offer", "platform"])
def test_hidden_content_is_not_exposed_by_description_or_history(catalog_client, hidden_scope):
    client, engine, (_, product_id, shop_id, offer_id) = catalog_client
    with Session(engine) as db:
        if hidden_scope == "product":
            db.get(Product, product_id).is_visible = False
        elif hidden_scope == "offer":
            db.get(Offer, offer_id).hidden_reason = "Admin restriction"
        else:
            db.get(Shop, shop_id).platform = "dujiao_next"
        db.commit()
    assert client.get(f"/api/v1/offers/{offer_id}/description").status_code == 404
    history = client.get("/api/v1/products/review-product/history")
    assert history.status_code == 404 if hidden_scope == "product" else history.json()["trend"] == []


def test_shop_prices_only_compare_the_same_product(catalog_client):
    client, engine, (snapshot_id, _, shop_id, _) = catalog_client
    with Session(engine) as db:
        for index in range(2):
            product = Product(slug=f"expensive-{index}", platform="OpenAI", display_name=f"Expensive {index}")
            db.add(product)
            db.flush()
            raw = RawProduct(shop_id=shop_id, source_product_key=str(index), original_name=product.display_name)
            db.add(raw)
            db.flush()
            db.add(Offer(
                raw_product_id=raw.id, shop_id=shop_id, product_id=product.id, snapshot_id=snapshot_id,
                price=Decimal("100"), stock_status="in_stock", delivery_type="finished_account", is_comparable=True,
            ))
        db.commit()
    offers = client.get("/api/v1/shops/review-shop").json()["offers"]
    assert len(offers) == 3
    assert all(offer["is_trusted_price"] for offer in offers)


def test_expanded_groups_keep_exclusions_and_empty_fingerprint_identity(catalog_client):
    client, engine, (snapshot_id, product_id, shop_id, offer_id) = catalog_client
    with Session(engine) as db:
        raw = RawProduct(shop_id=shop_id, source_product_key="excluded", original_name="Excluded offer")
        db.add(raw)
        db.flush()
        db.add(Offer(raw_product_id=raw.id, shop_id=shop_id, product_id=product_id, snapshot_id=snapshot_id, item_fingerprint="same"))
        db.commit()
    response = client.get("/api/v1/products/review-product/groups/same", params={"exclude": "Excluded"})
    assert [offer["id"] for offer in response.json()["items"]] == [offer_id]
    with Session(engine) as db:
        db.get(Offer, offer_id).item_fingerprint = ""
        db.commit()
    fallback = client.get(f"/api/v1/products/review-product/groups/offer-{offer_id}")
    assert [offer["id"] for offer in fallback.json()["items"]] == [offer_id]


def test_nonfinite_watch_target_is_rejected(catalog_client):
    client, _, _ = catalog_client
    assert client.get("/api/v1/watch.atom", params={"targets": "review-product:NaN"}).status_code == 422


def test_offer_patch_rejects_null_flags_but_allows_clearing_reason(catalog_client):
    client, engine, (_, _, _, offer_id) = catalog_client
    for flag in ("active", "approved"):
        response = client.patch(f"/api/v1/admin/offers/{offer_id}", headers={"X-Admin-Key": "admin-test"}, json={flag: None})
        assert response.status_code == 422
    response = client.patch(f"/api/v1/admin/offers/{offer_id}", headers={"X-Admin-Key": "admin-test"}, json={"hidden_reason": None})
    assert response.status_code == 200
    with Session(engine) as db:
        assert db.get(Offer, offer_id).hidden_reason == ""


def test_blank_hidden_reason_remains_public(catalog_client):
    client, engine, (_, _, _, offer_id) = catalog_client
    with Session(engine) as db:
        db.get(Offer, offer_id).hidden_reason = "   "
        db.commit()
    assert client.get("/api/v1/products").json()["offer_count"] == 1
