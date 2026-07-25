from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, Product, RawProduct, Shop
from app.services.catalog import _plain_text, _raw_decimal, get_product_detail, get_product_offer_page


def test_original_description_is_converted_to_safe_plain_text():
    source = '<p>第一行<br>第二行 &amp; 说明</p><script>alert("x")</script><style>hidden</style>'
    assert _plain_text(source) == "第一行\n第二行 & 说明"


def test_invalid_market_price_is_not_exposed():
    assert _raw_decimal("199") == Decimal("199.00")
    assert _raw_decimal("联系店主") is None


def test_product_offers_are_returned_in_pages():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        shop = Shop(token="paged-shop", name="Paged shop", source_url="https://example.com")
        product = Product(slug="paged-product", platform="OpenAI", display_name="Paged product")
        db.add_all([shop, product])
        db.flush()
        for index in range(35):
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=str(index),
                original_name=f"Offer {index + 1}",
                raw_json={"description": "description"},
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(raw)
            db.flush()
            db.add(Offer(
                raw_product_id=raw.id,
                product_id=product.id,
                shop_id=shop.id,
                price=Decimal(index + 1),
                stock_status="in_stock",
                source_url="https://example.com/offer",
                observed_at=now,
            ))
        db.commit()

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.offer_count == 35
        assert len(detail.offers) == 30
        assert detail.offers[0].price == Decimal("1.00")

        next_page = get_product_offer_page(db, product.slug, offset=30, limit=30)
        assert next_page is not None
        assert len(next_page) == 5
        assert next_page[0].price == Decimal("31.00")
