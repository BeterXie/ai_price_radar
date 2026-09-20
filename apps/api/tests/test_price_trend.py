import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CatalogSnapshot, Offer, OfferHistory, Product, RawProduct, Shop
from app.services.catalog import _price_trend, clear_price_trend_cache


def _engine():
    return create_engine("sqlite://")


def _add_offer(
    db: Session,
    *,
    product: Product,
    snapshot: CatalogSnapshot,
    token: str,
    history: list[tuple[Decimal | None, str, datetime]],
    delivery_type: str = "finished_account",
    is_comparable: bool = True,
    approved: bool = True,
    visible: bool = True,
) -> Offer:
    shop = Shop(
        token=token,
        name=token,
        source_url=f"https://example.com/{token}",
        platform="ldxp",
        is_visible=visible,
    )
    db.add(shop)
    db.flush()
    raw = RawProduct(
        shop_id=shop.id,
        source_product_key=token,
        original_name=product.display_name,
        first_seen_at=history[0][2],
        last_seen_at=history[-1][2],
    )
    db.add(raw)
    db.flush()
    offer = Offer(
        snapshot_id=snapshot.id,
        raw_product_id=raw.id,
        product_id=product.id,
        shop_id=shop.id,
        price=history[-1][0],
        stock_status=history[-1][1],
        delivery_type=delivery_type,
        is_comparable=is_comparable,
        approved=approved,
        source_url=shop.source_url,
        observed_at=history[-1][2],
    )
    db.add(offer)
    db.flush()
    db.add_all([
        OfferHistory(
            offer_id=offer.id,
            price=price,
            stock_status=stock_status,
            observed_at=observed_at,
        )
        for price, stock_status, observed_at in history
    ])
    return offer


def test_price_trend_preserves_daily_counts_and_price_semantics():
    engine = _engine()
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    observed_at = now - timedelta(days=2)

    with Session(engine) as db:
        product = Product(slug="trend-semantics", platform="OpenAI", display_name="Trend semantics")
        snapshot = CatalogSnapshot(source="test", published_at=now)
        db.add_all([product, snapshot])
        db.flush()

        def history(*rows: tuple[Decimal | None, str]) -> list[tuple[Decimal | None, str, datetime]]:
            return [(price, stock_status, observed_at) for price, stock_status in rows]

        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="finished-accounts",
            history=history(
                (Decimal("0.50"), "in_stock"),
                (Decimal("20.00"), "in_stock"),
                (Decimal("20.00"), "in_stock"),
                (Decimal("30.00"), "in_stock"),
            ),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="credits",
            delivery_type="credits",
            history=history(
                (Decimal("100.00"), "in_stock"),
                (Decimal("110.00"), "in_stock"),
            ),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="not-comparable",
            is_comparable=False,
            history=history((Decimal("200.00"), "in_stock")),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="out-of-stock",
            history=history((Decimal("50.00"), "out_of_stock")),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="missing-price",
            history=history((None, "in_stock")),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="hidden",
            visible=False,
            history=history((Decimal("999.00"), "in_stock")),
        )
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="unapproved",
            approved=False,
            history=history((Decimal("888.00"), "in_stock")),
        )
        db.commit()

        trend = _price_trend(db, product.id)

    assert len(trend) == 1
    point = trend[0]
    assert point.bucket_at.date() == observed_at.date()
    assert point.observation_count == 9
    assert point.in_stock_count == 8
    assert point.trusted_lowest_price == Decimal("20.00")
    assert point.median_price == Decimal("25.00")


def test_price_trend_cache_reuses_results_until_cleared():
    engine = _engine()
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        product = Product(slug="trend-cache", platform="OpenAI", display_name="Trend cache")
        snapshot = CatalogSnapshot(source="test", published_at=now)
        db.add_all([product, snapshot])
        db.flush()
        offer = _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token="cache-shop",
            history=[(Decimal("20.00"), "in_stock", now)],
        )
        db.commit()

        first = _price_trend(db, product.id)
        db.add(OfferHistory(
            offer_id=offer.id,
            price=Decimal("30.00"),
            stock_status="in_stock",
            observed_at=now,
        ))
        db.commit()

        cached = _price_trend(db, product.id)
        assert cached is first
        assert cached[0].observation_count == 1

        clear_price_trend_cache()
        refreshed = _price_trend(db, product.id)

    assert refreshed is not first
    assert refreshed[0].observation_count == 2
    assert refreshed[0].median_price == Decimal("25.00")


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_price_trend_uses_postgres_utc_day_bucket():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    observed_at = now - timedelta(days=1)

    with Session(engine) as db:
        product = Product(
            slug=f"trend-postgres-{uuid4().hex}",
            platform="OpenAI",
            display_name="PostgreSQL trend",
        )
        snapshot = CatalogSnapshot(source="test", published_at=now)
        db.add_all([product, snapshot])
        db.flush()
        _add_offer(
            db,
            product=product,
            snapshot=snapshot,
            token=f"postgres-trend-{uuid4().hex}",
            history=[
                (Decimal("20.00"), "in_stock", observed_at.replace(hour=1)),
                (Decimal("30.00"), "in_stock", observed_at.replace(hour=23)),
            ],
        )
        db.commit()

        trend = _price_trend(db, product.id)

    engine.dispose()
    assert len(trend) == 1
    assert trend[0].bucket_at.date() == observed_at.date()
    assert trend[0].observation_count == 2
    assert trend[0].median_price == Decimal("25.00")
