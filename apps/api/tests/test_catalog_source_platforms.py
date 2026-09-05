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
        hidden_only = Shop(token="hidden-only-shop", name="Hidden only", source_url="https://hidden.example.com", platform="16688")
        hidden_product = Product(
            slug="hidden-only-product",
            platform="OpenAI",
            display_name="Hidden only product",
            is_visible=False,
        )
        db.add_all([old, current, openai, claude, hidden_product, ldxp, dujiao, woo, structured, old_feed, hidden_only])
        db.flush()
        _offer(db, snapshot=current, product=openai, shop=ldxp, key="openai-ldxp")
        _offer(db, snapshot=current, product=openai, shop=dujiao, key="openai-dujiao")
        _offer(db, snapshot=current, product=claude, shop=dujiao, key="claude-dujiao")
        _offer(db, snapshot=current, product=claude, shop=woo, key="claude-woo")
        _offer(db, snapshot=current, product=openai, shop=woo, key="openai-woo")
        _offer(db, snapshot=current, product=openai, shop=structured, key="openai-structured")
        _offer(db, snapshot=old, product=openai, shop=old_feed, key="old-feed")
        _offer(db, snapshot=current, product=hidden_product, shop=hidden_only, key="hidden-only")
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        # dujiao_next is disabled and must yield 0 public offers
        legacy = client.get("/api/v1/products", params={"platform": "OpenAI", "source_platform": "dujiao_next"})
        assert legacy.status_code == 200
        assert legacy.json()["offer_count"] == 0
        assert len(legacy.json()["items"]) == 0

        woo = client.get("/api/v1/products", params={"platform": "OpenAI", "source_platform": "woocommerce"})
        assert woo.status_code == 200
        assert woo.json()["offer_count"] == 1

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
        # dujiao_next must be excluded from public source platforms
        assert meta["source_platforms"] == [
            {"id": "ldxp", "label": "链动小铺"},
            {"id": "schema_org", "label": "独立站"},
            {"id": "woocommerce", "label": "WooCommerce"},
        ]

        # The legacy endpoint remains a flat token list (excluding disabled dujiao).
        legacy_shop_tokens = client.get("/api/v1/shops")
        assert legacy_shop_tokens.status_code == 200
        assert legacy_shop_tokens.json() == sorted(["ldxp-shop", "structured-shop", "woo-shop"])

        # The directory endpoint returns paginated shop cards.
        shops_res = client.get("/api/v1/shops/cards")
        assert shops_res.status_code == 200
        shops_data = shops_res.json()
        assert shops_data["total"] == 3  # ldxp, woo, structured (dujiao disabled, feed on old snapshot)
        tokens = [s["token"] for s in shops_data["items"]]
        assert "dujiao-shop" not in tokens
        assert "feed-shop" not in tokens

        # Shop detail for a disabled platform shop returns 404
        dujiao_detail = client.get("/api/v1/shops/dujiao-shop")
        assert dujiao_detail.status_code == 404

        # Active shop detail exposes stable standard-product links
        woo_detail = client.get("/api/v1/shops/woo-shop")
        assert woo_detail.status_code == 200
        assert {
            (product["slug"], product["display_name"], product["offer_count"], product["in_stock_count"])
            for product in woo_detail.json()["products"]
        } == {
            ("chatgpt-plus", "ChatGPT Plus", 1, 1),
            ("claude-pro", "Claude Pro", 1, 1),
        }

        # Test filter by source_platform for disabled platform returns empty
        dujiao_shops = client.get("/api/v1/shops/cards", params={"source_platform": "dujiao_next"}).json()
        assert dujiao_shops["total"] == 0
        assert dujiao_shops["items"] == []

        aliased_filter = client.get("/api/v1/shops/cards", params={"source_platform": "dujiao-next"}).json()
        assert aliased_filter["total"] == 0

        paged = client.get("/api/v1/shops/cards", params={"offset": 1, "limit": 2, "sort": "name"})
        assert paged.status_code == 200
        assert paged.json()["total"] == 3
        assert len(paged.json()["items"]) == 2
        assert [item["token"] for item in paged.json()["items"]] == ["structured-shop", "woo-shop"]

        meta_without_hidden_only_source = client.get("/api/v1/meta").json()
        assert {item["id"] for item in meta_without_hidden_only_source["source_platforms"]} == {
            "ldxp",
            "schema_org",
            "woocommerce",
        }

        # Test tokens-only legacy endpoint
        tokens_res = client.get("/api/v1/shops/tokens")
        assert tokens_res.status_code == 200
        assert tokens_res.json() == sorted(["ldxp-shop", "structured-shop", "woo-shop"])
    finally:
        app.dependency_overrides.clear()
