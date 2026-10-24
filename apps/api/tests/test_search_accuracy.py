from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop


@pytest.fixture
def search_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        now = datetime.now(timezone.utc)
        snapshot = CatalogSnapshot(source="test", published_at=now)
        shop = Shop(token="search-shop", name="微风 Store", source_url="https://shop.example.com", platform="16688")
        db.add_all([snapshot, shop])
        db.flush()
        for index, (slug, name, title, stock, period) in enumerate([
            ("claude-max-5x", "Claude Max 5x", "独享成品 月卡", "in_stock", "one_month"),
            ("claude-max-5x", "Claude Max 5x", "独享成品 周卡", "in_stock", "one_week"),
            ("claude-pro", "Claude Pro", "Student_% 月卡", "out_of_stock", "one_month"),
            ("chatgpt-plus", "ChatGPT Plus", "独享成品 月卡", "in_stock", "one_month"),
        ]):
            product = next((row for row in db.new if isinstance(row, Product) and row.slug == slug), None)
            from sqlalchemy import select
            product = product or db.scalar(select(Product).where(Product.slug == slug))
            if product is None:
                product = Product(slug=slug, platform="OpenAI" if slug.startswith("chatgpt") else "Claude", display_name=name)
                db.add(product)
                db.flush()
            raw = RawProduct(shop_id=shop.id, source_product_key=str(index), original_name=title)
            db.add(raw)
            db.flush()
            db.add(Offer(raw_product_id=raw.id, shop_id=shop.id, product_id=product.id, snapshot_id=snapshot.id,
                         price=Decimal("100"), currency="CNY", stock_status=stock, active=True, approved=True,
                         observed_at=now, is_comparable=True, delivery_type="finished_account", service_period=period,
                         item_fingerprint=f"search-{index}"))
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_words_match_across_fields_in_any_order_and_intersect_filters(search_client):
    response = search_client.get("/api/v1/products", params={"q": "月卡 Claude 微风", "in_stock": "true", "period": "one_month", "source_platform": "16688"})
    assert response.status_code == 200, response.text
    assert [row["slug"] for row in response.json()["items"]] == ["claude-max-5x"]
    assert response.json()["items"][0]["offer_count"] == 1
    assert search_client.get("/api/v1/products", params={"q": "微风 5x Claude"}).json()["total"] == 1


@pytest.mark.parametrize("query", ["%", "_", "Student_%"])
def test_search_treats_sql_wildcards_literally(search_client, query):
    response = search_client.get("/api/v1/products", params={"q": query})
    assert [row["slug"] for row in response.json()["items"]] == ["claude-pro"]


def test_product_detail_and_group_pagination_keep_the_same_search_scope(search_client):
    params = {"q": "月卡 5x", "in_stock": "true"}
    detail = search_client.get("/api/v1/products/claude-max-5x", params=params)
    assert detail.status_code == 200, detail.text
    assert detail.json()["offer_count"] == 1
    groups = search_client.get("/api/v1/products/claude-max-5x/groups", params={**params, "limit": 1})
    assert groups.json()["total"] == 1 and groups.json()["offer_total"] == 1
    assert len(groups.json()["items"]) == 1
    assert search_client.get("/api/v1/products/claude-max-5x/offers", params=params).json()["items"][0]["original_name"] == "独享成品 月卡"


def test_brand_alias_is_searchable_even_when_original_title_omits_it(search_client):
    response = search_client.get("/api/v1/products", params={"q": "openai 月卡"})
    assert [row["slug"] for row in response.json()["items"]] == ["chatgpt-plus"]


def test_flat_offer_page_intersects_keyword_and_period_filters(search_client):
    response = search_client.get("/api/v1/products/claude-max-5x/offers", params={"q": "微风 Claude", "period": "one_week", "in_stock": True})
    assert response.status_code == 200
    assert [row["original_name"] for row in response.json()["items"]] == ["独享成品 周卡"]
    assert search_client.get("/api/v1/products/claude-pro/offers", params={"q": "月卡", "in_stock": True}).json()["items"] == []
