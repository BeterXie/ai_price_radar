from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, Product, RawProduct, Shop
from app.services.catalog import _plain_text, _raw_decimal, get_group_offers, get_offer_description, get_product_detail, get_product_offer_page


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
                delivery_type="finished_account",
                is_comparable=True,
                item_fingerprint=f"fingerprint-{index}",
                source_url="https://example.com/offer",
                observed_at=now,
            ))
        db.commit()

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.offer_count == 35
        assert detail.offer_group_count == 35
        assert len(detail.offer_groups) == 30
        assert detail.offer_groups[0].lowest_price == Decimal("1.00")

        next_page = get_product_offer_page(db, product.slug, offset=30, limit=30)
        assert next_page is not None
        assert len(next_page) == 5
        assert next_page[0].price == Decimal("31.00")


def test_product_detail_uses_comparable_price_and_groups_duplicate_offers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        product = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        db.add(product)
        db.flush()
        specs = [
            ("shop-a", Decimal("20"), True, "finished_account", "same-fingerprint"),
            ("shop-b", Decimal("15"), True, "finished_account", "same-fingerprint"),
            ("shop-c", Decimal("2.60"), False, "relay_api", "relay-fingerprint"),
        ]
        offer_ids: list[int] = []
        for token, price, comparable, delivery_type, fingerprint in specs:
            shop = Shop(token=token, name=token, source_url=f"https://example.com/{token}")
            db.add(shop)
            db.flush()
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=token,
                original_name="ChatGPT Plus 成品号" if comparable else "纯 Plus 中转站",
                raw_json={"description": "账号密码交付，质保首登"},
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
                delivery_type=delivery_type,
                is_comparable=comparable,
                item_fingerprint=fingerprint,
                source_url=raw.source_url,
                observed_at=now,
            )
            db.add(offer)
            db.flush()
            offer_ids.append(offer.id)
        db.commit()

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.lowest_price == Decimal("15.00")
        assert detail.related_lowest_price == Decimal("2.60")
        assert detail.offer_count == 3
        assert detail.offer_group_count == 1
        assert detail.offer_groups[0].shop_count == 2
        assert detail.offer_groups[0].lowest_price == Decimal("15.00")
        assert detail.offer_groups[0].representative.original_description == ""

        grouped = get_group_offers(db, product.slug, "same-fingerprint")
        assert grouped is not None and len(grouped) == 2
        assert get_offer_description(db, offer_ids[0]) == "账号密码交付，质保首登"
