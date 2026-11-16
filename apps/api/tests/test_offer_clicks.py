import sys
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.core.config import get_settings
from app.main import app
from app.models import CatalogSnapshot, Offer, OfferClick, Product, RawProduct, Shop


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_catalog(db):
    now = datetime.now(timezone.utc)
    snapshot = CatalogSnapshot(source="test", offer_count=1, published_at=now)
    db.add(snapshot)
    db.flush()

    shop = Shop(
        token="shop-test-radar",
        name="测试雷达店铺",
        source_url="https://test-shop.com",
        platform="ldxp",
        status="normal",
        is_visible=True,
    )
    db.add(shop)
    db.flush()

    product = Product(
        slug="chatgpt-plus",
        platform="openai",
        display_name="ChatGPT Plus 独享账号",
        is_visible=True,
    )
    db.add(product)
    db.flush()

    raw_product = RawProduct(
        shop_id=shop.id,
        source_product_key="item-001",
        original_name="ChatGPT Plus 官方正版月付",
        original_category="AI会员",
        source_url="https://test-shop.com/item-001",
        raw_json={"description": "优质稳定独享号"},
    )
    db.add(raw_product)
    db.flush()

    offer = Offer(
        raw_product_id=raw_product.id,
        product_id=product.id,
        shop_id=shop.id,
        snapshot_id=snapshot.id,
        price=Decimal("120.00"),
        currency="CNY",
        stock_status="in_stock",
        stock_count=50,
        delivery_type="account",
        service_period="1mo",
        warranty="30d",
        is_comparable=True,
        source_url="https://test-shop.com/item-001",
        active=True,
        approved=True,
        click_count=0,
        observed_at=now,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    db.refresh(shop)
    db.refresh(product)
    return shop, product, offer


def test_recent_product_activity_uses_event_window_not_lifetime(client, test_db, monkeypatch):
    from app.routers import public

    shop, product, offer = _seed_catalog(test_db)
    now = datetime(2026, 11, 11, 8, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(public, "datetime", FrozenDateTime)
    offer.click_count = 9876
    hidden = Product(slug="private-product", platform="openai", display_name="隐藏", is_visible=False)
    quiet = Product(slug="quiet-product", platform="openai", display_name="暂无访问", is_visible=True)
    test_db.add_all([hidden, quiet])
    for created_at in [now, now - timedelta(days=7), now - timedelta(days=7, microseconds=1), now + timedelta(seconds=1)]:
        test_db.add(OfferClick(offer_id=offer.id, shop_id=shop.id, product_slug=product.slug, created_at=created_at))
    test_db.add(OfferClick(shop_id=shop.id, product_slug=product.slug, created_at=now))
    test_db.add(OfferClick(offer_id=offer.id, shop_id=shop.id, product_slug=hidden.slug, created_at=now))
    test_db.commit()

    response = client.get("/api/v1/catalog/activity")
    assert response.status_code == 200
    data = response.json()
    assert data["window_days"] == 7
    assert datetime.fromisoformat(data["end_at"].replace("Z", "+00:00")) - datetime.fromisoformat(data["start_at"].replace("Z", "+00:00")) == timedelta(days=7)
    assert {item["product_slug"]: item["click_count"] for item in data["items"]} == {product.slug: 2, quiet.slug: 0}


def test_record_offer_click_and_debounce(client, test_db):
    shop, product, offer = _seed_catalog(test_db)
    assert offer.click_count == 0

    # 1. First click
    res1 = client.post(f"/api/v1/offers/{offer.id}/click")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["recorded"] is True
    assert data1["click_count"] == 1

    test_db.refresh(offer)
    assert offer.click_count == 1

    # Check offer_clicks row
    clicks = list(test_db.scalars(select(OfferClick).where(OfferClick.offer_id == offer.id)))
    assert len(clicks) == 1
    assert clicks[0].shop_id == shop.id
    assert clicks[0].product_slug == "chatgpt-plus"
    expected_hash = hmac.new(
        get_settings().session_secret_key.encode("utf-8"),
        b"offer-click:testclient",
        hashlib.sha256,
    ).hexdigest()[:32]
    assert clicks[0].ip_hash == expected_hash

    # 2. Immediate second click from same IP (debounced within 60s)
    res2 = client.post(f"/api/v1/offers/{offer.id}/click")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["recorded"] is False
    assert data2["click_count"] == 1

    test_db.refresh(offer)
    assert offer.click_count == 1


def test_quote_activity_counts_each_group_and_offer_from_seven_day_events(client, test_db, monkeypatch):
    from app.routers import public

    shop, product, first = _seed_catalog(test_db)
    now = first.observed_at.replace(tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(public, "datetime", FrozenDateTime)
    first.item_fingerprint = "same-item"
    first.click_count = 9876

    def another(fingerprint, **overrides):
        raw = RawProduct(shop_id=shop.id, source_product_key=f"item-{len(test_db.new)}-{fingerprint}-{overrides}", original_name="报价")
        test_db.add(raw)
        test_db.flush()
        values = dict(raw_product_id=raw.id, product_id=product.id, shop_id=shop.id, snapshot_id=first.snapshot_id,
                      observed_at=now, item_fingerprint=fingerprint, active=True, approved=True)
        values.update(overrides)
        offer = Offer(**values)
        test_db.add(offer)
        test_db.flush()
        return offer

    second = another("same-item")
    different = another("different-item")
    empty_a = another("")
    empty_b = another("", price=Decimal("7"))
    hidden = another("same-item", hidden_reason="moderated")
    private_product = Product(slug="private", platform="openai", display_name="Hidden", is_visible=False)
    test_db.add(private_product)
    test_db.flush()
    private = another("same-item", product_id=private_product.id)

    def click(offer, when=now, slug=product.slug):
        test_db.add(OfferClick(offer_id=offer.id, shop_id=shop.id, product_slug=slug, created_at=when))

    click(first)
    click(first, now - timedelta(days=7))
    click(first, now - timedelta(days=7, microseconds=1))
    click(first, now + timedelta(seconds=1))
    click(first, slug="wrong-product")
    click(second)
    click(different)
    click(empty_a)
    click(hidden)
    click(private, slug=private_product.slug)
    test_db.add(OfferClick(shop_id=shop.id, product_slug=product.slug, created_at=now))
    test_db.commit()
    ids = [first.id, second.id, different.id, empty_a.id, empty_b.id, hidden.id, private.id, 999999]
    params = [("offer_id", id) for id in ids]
    response = client.get("/api/v1/offers/activity", params=params)
    assert response.status_code == 200
    data = response.json()
    assert data["window_days"] == 7
    assert {item["offer_id"]: item["click_count"] for item in data["items"]} == {
        first.id: 3, second.id: 3, different.id: 1, empty_a.id: 1, empty_b.id: 0,
    }
    response = client.get("/api/v1/offers/activity", params=params + [("grouped", "false")])
    assert {item["offer_id"]: item["click_count"] for item in response.json()["items"]} == {
        first.id: 2, second.id: 1, different.id: 1, empty_a.id: 1, empty_b.id: 0,
    }


@pytest.mark.parametrize("params", [[], [("offer_id", 0)], [("offer_id", 1)] * 101])
def test_quote_activity_requires_a_bounded_list_of_valid_ids(client, params):
    assert client.get("/api/v1/offers/activity", params=params).status_code == 422


def test_record_offer_click_not_found(client, test_db):
    res = client.post("/api/v1/offers/99999/click")
    assert res.status_code == 404


def test_hidden_offer_click_is_not_recorded(client, test_db):
    _, _, offer = _seed_catalog(test_db)
    offer.hidden_reason = "manual moderation"
    test_db.commit()
    response = client.post(f"/api/v1/offers/{offer.id}/click")
    assert response.status_code == 404
    assert test_db.scalar(select(OfferClick).where(OfferClick.offer_id == offer.id)) is None


def test_record_shop_click(client, test_db):
    shop, _, _ = _seed_catalog(test_db)

    # 1. First shop click
    res1 = client.post(f"/api/v1/shops/{shop.token}/click")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["recorded"] is True

    # 2. Debounced second click
    res2 = client.post(f"/api/v1/shops/{shop.token}/click")
    assert res2.status_code == 200
    assert res2.json()["recorded"] is False


def test_shop_detail_click_metrics(client, test_db):
    shop, product, offer = _seed_catalog(test_db)

    # Record 1 offer click and 1 shop click
    res_offer = client.post(f"/api/v1/offers/{offer.id}/click")
    assert res_offer.status_code == 200

    res_shop = client.post(f"/api/v1/shops/{shop.token}/click", headers={"X-Forwarded-For": "1.2.3.4"})
    assert res_shop.status_code == 200

    # Get shop detail
    res = client.get(f"/api/v1/shops/{shop.token}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["today_clicks"] == 2
    assert detail["total_clicks"] == 2
    assert len(detail["offers"]) == 1
    assert detail["offers"][0]["click_count"] == 1
    assert detail["offers"][0]["product_slug"] == product.slug
    assert detail["offers"][0]["product_name"] == product.display_name


def test_product_offers_and_groups_contain_click_count(client, test_db):
    shop, product, offer = _seed_catalog(test_db)
    client.post(f"/api/v1/offers/{offer.id}/click")

    # Product offers endpoint
    res_offers = client.get(f"/api/v1/products/{product.slug}/offers")
    assert res_offers.status_code == 200
    items = res_offers.json()["items"]
    assert len(items) == 1
    assert items[0]["click_count"] == 1

    # Product groups endpoint
    res_groups = client.get(f"/api/v1/products/{product.slug}/groups")
    assert res_groups.status_code == 200
    groups = res_groups.json()["items"]
    assert len(groups) == 1
    assert groups[0]["representative"]["click_count"] == 1
    assert groups[0]["click_count"] == 1
