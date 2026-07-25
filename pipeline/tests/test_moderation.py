from common import Offer, Shop, ensure_products, session_for, upsert_offer


def test_reimport_preserves_moderation_state():
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        record = {
            "token": "TEST-SHOP",
            "shop_name": "Test Shop",
            "shop_url": "https://example.invalid/shop/test",
            "product_key": "test-product",
            "product_name": "ChatGPT Plus 直充一个月",
            "product_url": "https://example.invalid/item/test",
            "listed_price": "88.00",
            "stock_count": "1",
            "product_status": "有货",
            "collected_at": "2026-07-26T00:00:00+00:00",
        }
        upsert_offer(db, record, products)
        db.commit()

        shop = db.query(Shop).filter_by(token="TEST-SHOP").one()
        offer = db.query(Offer).filter_by(shop_id=shop.id).one()
        offer.active = False
        offer.approved = False
        offer.hidden_reason = "manual moderation"
        db.commit()

        upsert_offer(db, record, products)
        db.commit()
        db.refresh(offer)

        assert offer.active is False
        assert offer.approved is False
        assert offer.hidden_reason == "manual moderation"
    finally:
        db.close()
