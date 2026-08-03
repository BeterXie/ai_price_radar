import pytest

from common import CatalogSnapshot, Offer, OfferHistory, begin_snapshot, ensure_products, session_for, upsert_offer, utcnow


def record(name: str = "ChatGPT Plus 直充一个月") -> dict:
    return {
        "token": "SNAPSHOT-SHOP",
        "shop_name": "Snapshot Shop",
        "shop_url": "https://example.invalid/shop",
        "product_key": "snapshot-product",
        "product_name": name,
        "product_url": "https://example.invalid/item",
        "listed_price": "88.00",
        "stock_count": "1",
        "product_status": "有货",
        "collected_at": "2026-07-26T00:00:00+00:00",
    }


def test_failed_snapshot_rolls_back_offer_version_switch():
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        first = begin_snapshot(db, "test")
        upsert_offer(db, record(), products, first.id)
        first.offer_count = 1
        first.published_at = utcnow()
        db.commit()

        second = begin_snapshot(db, "test")
        upsert_offer(db, record(), products, second.id)
        db.rollback()

        offer = db.query(Offer).one()
        published = db.query(CatalogSnapshot).filter(CatalogSnapshot.published_at.isnot(None)).all()
        assert offer.snapshot_id == first.id
        assert [snapshot.id for snapshot in published] == [first.id]
    finally:
        db.close()


def test_low_confidence_new_offer_stays_pending_review():
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        low_confidence = record("高级会员直充一个月")
        low_confidence["category_name"] = "Claude"
        upsert_offer(db, low_confidence, products)
        offer = db.query(Offer).one()
        assert offer.product_id == products["claude-account"].id
        assert offer.classification_confidence == 68
        assert offer.approved is False
    finally:
        db.close()


def test_offer_and_history_preserve_valid_currency_changes():
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        usd = record()
        usd["currency"] = "usd"
        _, first_changed = upsert_offer(db, usd, products)
        db.commit()

        offer = db.query(Offer).one()
        assert first_changed is True
        assert offer.currency == "USD"
        assert [row.currency for row in db.query(OfferHistory).all()] == ["USD"]

        eur = record()
        eur["currency"] = "EUR"
        _, second_changed = upsert_offer(db, eur, products)
        db.commit()

        assert second_changed is True
        assert offer.currency == "EUR"
        assert [row.currency for row in db.query(OfferHistory).order_by(OfferHistory.id)] == ["USD", "EUR"]

        invalid = record("ChatGPT Plus 直充三个月")
        invalid["product_key"] = "invalid-currency"
        invalid["currency"] = "USDT"
        with pytest.raises(ValueError, match="unsupported currency"):
            upsert_offer(db, invalid, products)
    finally:
        db.close()


@pytest.mark.parametrize(("raw_delivery", "expected"), [
    (True, True),
    (False, False),
    (None, None),
    ("否", False),
    ("false", False),
])
def test_upsert_offer_preserves_delivery_state(raw_delivery, expected):
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        source_record = record()
        source_record["auto_delivery"] = raw_delivery

        upsert_offer(db, source_record, products)

        assert db.query(Offer).one().auto_delivery is expected
    finally:
        db.close()
