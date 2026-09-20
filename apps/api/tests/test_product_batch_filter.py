from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop, SystemSetting


def test_products_batch_filter_and_public_url_sanitization() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        snapshot = CatalogSnapshot(source="batch-filter", published_at=now)
        unsafe_url = "javascript:alert(1)"
        shop = Shop(
            token="batch-shop",
            name="Batch shop",
            source_url=unsafe_url,
            platform="schema_org",
        )
        product_slugs = (
            "alpha-product",
            "beta-product",
            "gamma-product",
            *(f"bulk-product-{index:02d}" for index in range(55)),
        )
        products = [
            Product(slug=slug, platform="OpenAI", display_name=slug.title())
            for slug in product_slugs
        ]
        db.add_all([snapshot, shop, *products])
        db.flush()

        for product in products:
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=product.slug,
                original_name=product.display_name,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(raw)
            db.flush()
            db.add(Offer(
                raw_product_id=raw.id,
                product_id=product.id,
                shop_id=shop.id,
                snapshot_id=snapshot.id,
                price=Decimal("20.00"),
                stock_status="in_stock",
                is_comparable=True,
                item_fingerprint=product.slug,
                source_url=unsafe_url,
                observed_at=now,
            ))

        db.add_all([
            SystemSetting(key="site_notice_link_url", value="//untrusted.example/path"),
            SystemSetting(key="community_qq_url", value="javascript:alert(1)"),
        ])
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/products",
            params={"products": "gamma-product,alpha-product,alpha-product"},
        )
        assert response.status_code == 200
        assert {item["slug"] for item in response.json()["items"]} == {
            "alpha-product",
            "gamma-product",
        }

        first_page = client.get("/api/v1/products", params={"limit": 20})
        assert first_page.status_code == 200
        assert first_page.json()["total"] == len(product_slugs)
        assert len(first_page.json()["items"]) == 20
        last_page = client.get("/api/v1/products", params={"offset": 50, "limit": 20})
        assert last_page.status_code == 200
        assert last_page.json()["total"] == len(product_slugs)
        assert len(last_page.json()["items"]) == len(product_slugs) - 50

        too_many = ",".join(f"product-{index}" for index in range(21))
        assert client.get("/api/v1/products", params={"products": too_many}).status_code == 422
        assert client.get("/api/v1/products", params={"products": "alpha-product,bad_slug"}).status_code == 422

        detail = client.get("/api/v1/shops/batch-shop")
        assert detail.status_code == 200
        assert detail.json()["offer_count"] == len(product_slugs)
        assert len(detail.json()["offers"]) == 30
        assert detail.json()["source_url"] == ""
        assert {offer["source_url"] for offer in detail.json()["offers"]} == {""}

        next_offers = client.get(
            "/api/v1/shops/batch-shop",
            params={"offer_offset": 30, "offer_limit": 30},
        )
        assert next_offers.status_code == 200
        assert next_offers.json()["offer_count"] == len(product_slugs)
        assert len(next_offers.json()["offers"]) == len(product_slugs) - 30

        cards = client.get("/api/v1/shops/cards")
        assert cards.status_code == 200
        assert cards.json()["items"][0]["source_url"] == ""

        meta = client.get("/api/v1/meta")
        assert meta.status_code == 200
        assert meta.json()["site_notice"]["link_url"] == ""
        assert meta.json()["community_notice"]["qq_url"] == ""
    finally:
        app.dependency_overrides.clear()
