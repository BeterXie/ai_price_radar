from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop


def _offer(db: Session, *, snapshot: CatalogSnapshot, product: Product, shop: Shop, key: str) -> None:
    now = datetime.now(timezone.utc)
    raw = RawProduct(
        shop_id=shop.id,
        source_product_key=key,
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
        price=Decimal("20"),
        stock_status="in_stock",
        is_comparable=True,
        item_fingerprint=key,
        snapshot_id=snapshot.id,
        source_url=shop.source_url,
        observed_at=now,
    ))


def test_catalog_api_separates_brand_and_current_snapshot_source_platforms():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        current = CatalogSnapshot(source="combined", published_at=now)
        old = CatalogSnapshot(source="old", published_at=now - timedelta(days=1))
        openai = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        claude = Product(slug="claude-pro", platform="Claude", display_name="Claude Pro")
        ldxp = Shop(token="ldxp-shop", name="LDXP", source_url="https://pay.ldxp.cn/shop/example", platform="ldxp")
        dujiao = Shop(token="dujiao-shop", name="Dujiao", source_url="https://shop.example.com", platform="dujiao_next")
        woo = Shop(token="woo-shop", name="Woo", source_url="https://woo.example.com", platform="woocommerce")
        structured = Shop(token="structured-shop", name="Structured", source_url="https://structured.example.com", platform="schema_org")
        old_feed = Shop(token="feed-shop", name="Feed", source_url="https://feed.example.com/catalog.json", platform="merchant_json")
        db.add_all([old, current, openai, claude, ldxp, dujiao, woo, structured, old_feed])
        db.flush()
        _offer(db, snapshot=current, product=openai, shop=ldxp, key="openai-ldxp")
        _offer(db, snapshot=current, product=openai, shop=dujiao, key="openai-dujiao")
        _offer(db, snapshot=current, product=claude, shop=dujiao, key="claude-dujiao")
        _offer(db, snapshot=current, product=openai, shop=woo, key="openai-woo")
        _offer(db, snapshot=current, product=openai, shop=structured, key="openai-structured")
        _offer(db, snapshot=old, product=openai, shop=old_feed, key="old-feed")
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        legacy = client.get("/api/v1/products", params={"platform": "OpenAI", "source_platform": "dujiao_next"})
        assert legacy.status_code == 200
        assert legacy.json()["offer_count"] == 1
        assert legacy.json()["items"][0]["platform"] == "OpenAI"
        assert legacy.json()["items"][0]["brand"] == "OpenAI"

        combined = client.get(
            "/api/v1/catalog/groups",
            params={"brand": "OpenAI", "product": "chatgpt-plus", "source_platform": "ldxp"},
        )
        assert combined.status_code == 200
        assert combined.json()["offer_total"] == 1
        representative = combined.json()["items"][0]["representative"]
        assert representative["source_platform"] == "ldxp"
        assert representative["source_platform_label"] == "链动小铺"
        assert representative["source_kind"] == "public_page"

        meta = client.get("/api/v1/meta").json()
        assert meta["platforms"] == meta["brands"] == ["Claude", "OpenAI"]
        assert meta["source_platforms"] == [
            {"id": "dujiao_next", "label": "Dujiao-Next"},
            {"id": "ldxp", "label": "链动小铺"},
            {"id": "schema_org", "label": "独立站"},
            {"id": "woocommerce", "label": "WooCommerce"},
        ]
    finally:
        app.dependency_overrides.clear()
