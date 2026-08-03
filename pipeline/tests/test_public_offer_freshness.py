from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from common import CatalogSnapshot, Offer, Product, RawProduct, Shop, session_for, utcnow
from connectors import CONNECTORS
from publish_catalog import (
    SourceSpec,
    approved_intake_sources,
    public_offer_count,
    publish_sources,
)


def _add_offer(db, *, token: str, observed_at):
    snapshot = CatalogSnapshot(source=f"source-{token}")
    shop = Shop(
        token=token,
        name=f"Shop {token}",
        source_url=f"https://{token}.example",
        platform="merchant_json",
        is_visible=True,
    )
    product = Product(
        slug=f"product-{token}",
        platform="chatgpt",
        display_name=f"ChatGPT Plus {token}",
    )
    db.add_all([snapshot, shop, product])
    db.flush()
    raw = RawProduct(
        shop_id=shop.id,
        source_product_key=f"upstream-{token}",
        original_name=product.display_name,
        source_url=f"https://{token}.example/product",
    )
    db.add(raw)
    db.flush()
    offer = Offer(
        raw_product_id=raw.id,
        product_id=product.id,
        shop_id=shop.id,
        snapshot_id=snapshot.id,
        source_url=raw.source_url,
        observed_at=observed_at,
        active=True,
        approved=True,
    )
    db.add(offer)
    db.flush()
    return snapshot, offer


def _create_source_intakes(db) -> None:
    db.execute(text(
        "CREATE TABLE source_intakes ("
        "id INTEGER PRIMARY KEY, source_type TEXT NOT NULL, detected_platform TEXT NOT NULL, "
        "source_url TEXT NOT NULL, status TEXT NOT NULL, product_count INTEGER NOT NULL DEFAULT 0, "
        "finished_at TEXT, updated_at TEXT)"
    ))
    db.execute(text(
        "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
        "VALUES (1, 'merchant_json', 'merchant_json', 'https://feed.example/catalog.json', 'approved')"
    ))
    db.commit()


def test_public_offer_count_excludes_stale_offer_and_includes_fresh_offer(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STALE_OFFER_HOURS", "72")
    now = utcnow()
    db = session_for("sqlite://")
    try:
        stale_snapshot, stale_offer = _add_offer(
            db,
            token="stale",
            observed_at=now - timedelta(hours=73),
        )
        fresh_snapshot, fresh_offer = _add_offer(
            db,
            token="fresh",
            observed_at=now - timedelta(hours=71),
        )

        assert public_offer_count(
            db,
            snapshot_id=stale_snapshot.id,
            offer_ids={stale_offer.id},
            now=now,
        ) == 0
        assert public_offer_count(
            db,
            snapshot_id=fresh_snapshot.id,
            offer_ids={fresh_offer.id},
            now=now,
        ) == 1
    finally:
        db.close()


@pytest.mark.parametrize(
    ("observed_age", "expected_count", "expected_status"),
    [
        (timedelta(hours=73), 0, "no_products"),
        (timedelta(minutes=1), 1, "published"),
    ],
)
def test_intake_is_published_only_when_imported_offer_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
    observed_age: timedelta,
    expected_count: int,
    expected_status: str,
):
    monkeypatch.setenv("STALE_OFFER_HOURS", "72")

    def loader(_source: str | Path):
        yield {
            "token": "freshness-shop",
            "shop_name": "Freshness Shop",
            "shop_url": "https://freshness.example",
            "source_platform": "merchant_json",
            "product_key": "chatgpt-plus",
            "product_name": "ChatGPT Plus 直充一个月",
            "product_url": "https://freshness.example/product",
            "listed_price": "88.00",
            "currency": "CNY",
            "stock_count": 1,
            "product_status": "in_stock",
            "collected_at": (utcnow() - observed_age).isoformat(),
        }

    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)
    db = session_for("sqlite://")
    try:
        _create_source_intakes(db)

        result = publish_sources(db, approved_intake_sources(db))

        assert result.imports[0].public_offer_count == expected_count
        assert db.execute(text(
            "SELECT status, product_count FROM source_intakes WHERE id=1"
        )).one() == (expected_status, expected_count)
    finally:
        db.close()
