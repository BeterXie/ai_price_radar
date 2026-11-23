from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop


@pytest.fixture
def search_db():
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
            ("gemini-pro", "Gemini Pro", "年度订阅", "in_stock", "one_year"),
            ("x-premium", "X Premium", "高级会员", "in_stock", "one_year"),
        ]):
            product = next((row for row in db.new if isinstance(row, Product) and row.slug == slug), None)
            product = product or db.scalar(select(Product).where(Product.slug == slug))
            if product is None:
                brand = {"chatgpt": "OpenAI", "claude": "Claude", "gemini": "Gemini", "x": "X"}[slug.split("-")[0]]
                product = Product(slug=slug, platform=brand, display_name=name)
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

    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def search_client(search_db):
    def override_db():
        with search_db() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def mailbox_client(search_client, search_db):
    with search_db() as db:
        snapshot = db.scalar(select(CatalogSnapshot))
        shop = Shop(token="mail-search", name="邮箱成品号小店", source_url="https://mail-shop.example", platform="16688")
        db.add(shop)
        db.flush()
        for slug, brand, name, title, delivery in [
            ("email-gmail", "邮箱", "Gmail / Google 邮箱", "独享长效 Google 邮箱，支持 ChatGPT 注册", "finished_account"),
            ("email-outlook", "邮箱", "Outlook / Hotmail 邮箱", "微软邮箱成品号", "finished_account"),
            ("chatgpt-account", "OpenAI", "ChatGPT Free", "现货独享，自带 Gmail 邮箱", "finished_account"),
            ("claude-account", "Claude", "Claude 账号", "半成品号 · Gmail 邮箱交付", "semi_finished_account"),
            ("verification-google", "接码 / 验证", "Google 验证", "Gmail 接码服务", "verification_service"),
        ]:
            product = Product(slug=slug, platform=brand, display_name=name)
            db.add(product)
            db.flush()
            raw = RawProduct(shop_id=shop.id, source_product_key=slug, original_name=title)
            db.add(raw)
            db.flush()
            db.add(Offer(raw_product_id=raw.id, shop_id=shop.id, product_id=product.id, snapshot_id=snapshot.id,
                         price=Decimal("12"), currency="CNY", stock_status="in_stock", active=True, approved=True,
                         observed_at=snapshot.published_at, is_comparable=True, delivery_type=delivery,
                         item_fingerprint=slug))
        db.commit()
    return search_client


@pytest.mark.parametrize(("q", "expected"), [
    ("邮箱", {"email-gmail", "email-outlook"}),
    ("Ｇｍａｉｌ", {"email-gmail"}),
    ("谷歌 邮箱", {"email-gmail"}),
    ("独享 Gmail", {"email-gmail"}),
    ("长效邮箱", {"email-gmail"}),
    ("邮箱账号", {"email-gmail", "email-outlook"}),
    ("邮箱 成品号", {"email-gmail", "email-outlook"}),
    ("Outlook邮箱成品号", {"email-outlook"}),
    ("Gmail 接码", {"verification-google"}),
    ("ChatGPT成品号 Gmail", {"chatgpt-account"}),
])
def test_mailbox_search_uses_product_identity_before_title_or_shop(mailbox_client, q, expected):
    for path, key in [("products", "slug"), ("catalog/groups", "product_slug")]:
        res = mailbox_client.get("/api/v1/" + path, params={"q": q, "comparable": True})
        assert res.status_code == 200, res.text
        assert {row[key] for row in res.json()["items"]} == expected


def test_finished_accounts_use_delivery_and_respect_explicit_mailbox_scope(mailbox_client):
    q = {"q": "成品号", "source_platform": "16688"}
    groups = mailbox_client.get("/api/v1/catalog/groups", params=q).json()["items"]
    assert all(row["representative"]["delivery_type"] == "finished_account" for row in groups)
    assert "chatgpt-account" in {row["product_slug"] for row in groups}
    assert not {row["product_slug"] for row in groups} & {"email-gmail", "email-outlook", "claude-account", "verification-google"}
    scoped = mailbox_client.get("/api/v1/catalog/groups", params={**q, "brand": "邮箱"}).json()
    assert {r["product_slug"] for r in scoped["items"]} == {"email-gmail", "email-outlook"}
    for slug, query in [("email-gmail", "成品号"), ("chatgpt-account", "Gmail")]:
        for path in ["", "/groups", "/offers", "/groups/" + slug]:
            res = mailbox_client.get(f"/api/v1/products/{slug}{path}", params={"q": query})
            assert res.status_code == 200, res.text
            data = res.json()
            if not path:
                assert data["offer_count"] == 1
            else:
                assert len(data["items"]) == 1


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


@pytest.mark.parametrize(("query", "slug"), [
    ("chatgptplus", "chatgpt-plus"),
    ("Claude Max5x", "claude-max-5x"),
    ("Ｃｌａｕｄｅ\u3000Ｍａｘ５ｘ", "claude-max-5x"),
    ("Claude\u200b Max5x", "claude-max-5x"),
    ("谷歌AI", "gemini-pro"),
    ("谷歌 AI", "gemini-pro"),
    ("Google AI", "gemini-pro"),
    ("Google One AI", "gemini-pro"),
    ("google", "gemini-pro"),
    ("推特", "x-premium"),
    ("twitter", "x-premium"),
])
def test_common_aliases_and_compact_plan_names_match_catalog_and_product_search(search_client, query, slug):
    cards = search_client.get("/api/v1/products", params={"q": query})
    assert cards.status_code == 200, cards.text
    assert [row["slug"] for row in cards.json()["items"]] == [slug]
    groups = search_client.get("/api/v1/catalog/groups", params={"q": query})
    assert groups.status_code == 200, groups.text
    assert groups.json()["total"] > 0
    detail = search_client.get(f"/api/v1/products/{slug}", params={"q": query})
    assert detail.status_code == 200, detail.text
    assert detail.json()["offer_count"] == cards.json()["items"][0]["offer_count"]


def test_compact_search_keeps_plan_and_scope_boundaries(search_client):
    assert search_client.get("/api/v1/products", params={"q": "Claude Max20x"}).json()["total"] == 0
    response = search_client.get("/api/v1/catalog/groups", params={"q": "Max5x 微风", "brand": "Claude", "period": "one_week", "in_stock": True})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert search_client.get("/api/v1/catalog/groups", params={"q": "Max5x", "brand": "OpenAI"}).json()["total"] == 0
