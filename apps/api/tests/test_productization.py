from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Offer, OfferHistory, Product, RawProduct, Report, Shop, SourceIntake
from app.services.catalog import get_product_detail, list_product_cards
from app.services.source_health import source_health


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _seed_product(db: Session, *, slug: str = "chatgpt-plus") -> Product:
    now = datetime.now(timezone.utc)
    product = Product(slug=slug, platform="OpenAI", display_name="ChatGPT Plus")
    db.add(product)
    db.flush()
    for index, price in enumerate((Decimal("0.01"), Decimal("15"), Decimal("20"))):
        shop = Shop(
            token=f"shop-{index}",
            name=f"Shop {index}",
            source_url=f"https://example.com/{index}",
            status="success",
            last_success_at=now,
        )
        db.add(shop)
        db.flush()
        raw = RawProduct(
            shop_id=shop.id,
            source_product_key=str(index),
            original_name="ChatGPT Plus 成品号",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(raw)
        db.flush()
        offer = Offer(
            raw_product_id=raw.id,
            product_id=product.id,
            shop_id=shop.id,
            price=price,
            stock_status="in_stock",
            delivery_type="finished_account",
            is_comparable=True,
            item_fingerprint=f"fingerprint-{index}",
            source_url=shop.source_url,
            observed_at=now,
        )
        db.add(offer)
        db.flush()
        db.add(OfferHistory(
            offer_id=offer.id,
            price=price,
            stock_status="in_stock",
            observed_at=now - timedelta(days=1),
        ))
    db.commit()
    return product


def test_product_exposes_official_reference_quality_and_aggregated_trend():
    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = _seed_product(db)
        cards = list_product_cards(db, product_slug=product.slug)
        assert cards[0].official_reference is not None
        assert cards[0].official_reference.price == Decimal("20.00")
        assert cards[0].source_count == 3
        assert cards[0].data_quality_score >= 55

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.trend
        assert detail.trend[-1].trusted_lowest_price == Decimal("15.00")
        assert detail.trend[-1].median_price == Decimal("15.00")


def test_source_health_is_factual_and_penalizes_scan_failures():
    now = datetime.now(timezone.utc)
    healthy = Shop(
        token="healthy",
        source_url="https://example.com",
        status="success",
        last_success_at=now,
        consecutive_failures=0,
    )
    unhealthy = Shop(
        token="unhealthy",
        source_url="https://example.com",
        status="blocked",
        last_success_at=now - timedelta(days=8),
        consecutive_failures=4,
    )
    assert source_health(healthy, now=now).label == "稳定"
    result = source_health(unhealthy, now=now)
    assert result.label == "需复核"
    assert result.score < 50
    assert any("失败" in reason for reason in result.reasons)


def test_public_corrections_hide_private_report_message_and_contact():
    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Report(
            kind="correction",
            message="private raw report",
            contact="private@example.com",
            status="resolved",
            public_summary="报价期限已由未知修正为一个月。",
            merchant_response="商家确认页面标注已更新。",
            resolved_at=datetime.now(timezone.utc),
        ))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/v1/corrections")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        item = payload["items"][0]
        assert item["public_summary"].startswith("报价期限")
        assert "message" not in item
        assert "contact" not in item
    finally:
        app.dependency_overrides.clear()


def test_watch_atom_feed_contains_threshold_state():
    engine = _engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_product(db)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/v1/watch.atom?targets=chatgpt-plus:16")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/atom+xml")
        assert "达到提醒条件" in response.text
        assert "CNY 15.00" in response.text
    finally:
        app.dependency_overrides.clear()


def test_merchant_feed_submission_accepts_public_https_and_rejects_private_host(monkeypatch):
    engine = _engine()
    Base.metadata.create_all(engine)

    from app.routers import public
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 10)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        accepted = client.post("/api/v1/shop-requests", json={
            "source_type": "merchant_feed",
            "shop_url": "https://merchant.example/catalog.json",
            "shop_name": "Merchant",
            "contact": "merchant@example.com",
        })
        assert accepted.status_code == 201
        assert accepted.json()["source_type"] == "merchant_feed"
        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake))
            assert intake is not None
            assert intake.source_type == "unknown"
            assert intake.declared_platform == "merchant_json"
            assert intake.detected_platform == "unknown"
            assert intake.source_key == "https://merchant.example/catalog.json"
            assert intake.status == "submitted"

        rejected = client.post("/api/v1/shop-requests", json={
            "source_type": "merchant_feed",
            "shop_url": "https://127.0.0.1/catalog.json",
        })
        assert rejected.status_code == 422
    finally:
        app.dependency_overrides.clear()
