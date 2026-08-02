from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, OfferHistory, Product, RawProduct, Shop
from app.services.catalog import (
    OfferFilters,
    _plain_text,
    _raw_decimal,
    get_catalog_group_page,
    get_group_offers,
    get_offer_description,
    get_product_detail,
    get_product_group_page,
    get_product_offer_page,
    list_product_cards,
)


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
                price=Decimal(index + 100),
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
        assert detail.offer_groups[0].lowest_price == Decimal("100.00")

        next_page = get_product_offer_page(db, product.slug, offset=30, limit=30)
        assert next_page is not None
        assert len(next_page) == 5
        assert next_page[0].price == Decimal("130.00")


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
        assert detail.offer_groups[0].product_slug == "chatgpt-plus"
        assert detail.offer_groups[0].shop_count == 2
        assert detail.offer_groups[0].lowest_price == Decimal("15.00")
        assert detail.offer_groups[0].representative.original_description == ""

        grouped = get_group_offers(db, product.slug, "same-fingerprint")
        assert grouped is not None and len(grouped) == 2
        assert get_offer_description(db, offer_ids[0]) == "账号密码交付，质保首登"


def test_warranty_scope_filters_groups_and_expanded_offers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        product = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        db.add(product)
        db.flush()
        for index, warranty in enumerate(("first_login", "none", "unknown")):
            shop = Shop(token=f"warranty-{index}", name=f"Warranty {index}", source_url=f"https://example.com/{index}")
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
            db.add(Offer(
                raw_product_id=raw.id,
                product_id=product.id,
                shop_id=shop.id,
                price=Decimal("20") + index,
                stock_status="in_stock",
                delivery_type="finished_account",
                warranty=warranty,
                is_comparable=True,
                item_fingerprint="same-fingerprint",
                source_url=shop.source_url,
                observed_at=now,
            ))
        db.commit()

        covered_groups, covered_total, _ = get_product_group_page(
            db,
            product.id,
            offset=0,
            limit=30,
            filters=OfferFilters(warranty="covered"),
        )
        assert covered_total == 1
        assert covered_groups[0].offer_count == 1
        covered_offers = get_group_offers(db, product.slug, "same-fingerprint", filters=OfferFilters(warranty="covered"))
        assert covered_offers is not None and [offer.warranty for offer in covered_offers] == ["first_login"]

        no_warranty_groups, no_warranty_total, _ = get_product_group_page(
            db,
            product.id,
            offset=0,
            limit=30,
            filters=OfferFilters(warranty="none"),
        )
        assert no_warranty_total == 1
        assert no_warranty_groups[0].offer_count == 1
        no_warranty_offers = get_group_offers(db, product.slug, "same-fingerprint", filters=OfferFilters(warranty="none"))
        assert no_warranty_offers is not None and [offer.warranty for offer in no_warranty_offers] == ["none"]


def test_catalog_groups_keep_products_separate_and_filter_platforms():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        products = [
            Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus"),
            Product(slug="claude-pro", platform="Claude", display_name="Claude Pro"),
        ]
        db.add_all(products)
        db.flush()
        for index, product in enumerate(products):
            shop = Shop(token=f"shop-{index}", name=f"Shop {index}", source_url=f"https://example.com/{index}")
            db.add(shop)
            db.flush()
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=str(index),
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
                price=Decimal("20") + index,
                stock_status="in_stock",
                is_comparable=True,
                item_fingerprint="shared-fingerprint",
                source_url=shop.source_url,
                observed_at=now,
            ))
        extra_shop = Shop(token="shop-extra", name="Extra", source_url="https://example.com/extra")
        db.add(extra_shop)
        db.flush()
        extra_raw = RawProduct(
            shop_id=extra_shop.id,
            source_product_key="extra",
            original_name="不可直接比较的中转服务",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(extra_raw)
        db.flush()
        db.add(Offer(
            raw_product_id=extra_raw.id,
            product_id=products[0].id,
            shop_id=extra_shop.id,
            price=Decimal("1"),
            stock_status="in_stock",
            is_comparable=False,
            item_fingerprint="relay-fingerprint",
            source_url=extra_shop.source_url,
            observed_at=now,
        ))
        db.commit()

        groups, total, offer_total, in_stock_count, comparable_count, trusted_count, _ = get_catalog_group_page(
            db,
            offset=0,
            limit=30,
            filters=OfferFilters(comparable=True),
        )
        assert total == 2
        assert offer_total == 2
        assert in_stock_count == 2
        assert comparable_count == 2
        assert trusted_count == 2
        assert {group.product_slug for group in groups} == {"chatgpt-plus", "claude-pro"}

        all_groups, all_total, all_offer_total, _, _, _, _ = get_catalog_group_page(
            db,
            offset=0,
            limit=30,
            filters=OfferFilters(),
        )
        assert all_total == 3
        assert all_offer_total == 3
        assert len(all_groups) == 3

        claude_groups, claude_total, _, _, _, _, _ = get_catalog_group_page(
            db,
            platform="Claude",
            offset=0,
            limit=30,
            filters=OfferFilters(comparable=True),
        )
        assert claude_total == 1
        assert claude_groups[0].product_name == "Claude Pro"



def test_trusted_price_excludes_extreme_comparable_outlier():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        product = Product(slug="trusted-product", platform="OpenAI", display_name="Trusted product")
        db.add(product)
        db.flush()
        for index, price in enumerate((Decimal("0.01"), Decimal("15"), Decimal("20"))):
            shop = Shop(token=f"trusted-{index}", name=f"Trusted {index}", source_url=f"https://example.com/{index}")
            db.add(shop)
            db.flush()
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=str(index),
                original_name="Trusted product account",
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(raw)
            db.flush()
            db.add(Offer(
                raw_product_id=raw.id,
                product_id=product.id,
                shop_id=shop.id,
                price=price,
                stock_status="in_stock",
                delivery_type="finished_account",
                is_comparable=True,
                item_fingerprint=f"trusted-{index}",
                source_url=shop.source_url,
                observed_at=now,
            ))
        db.commit()

        cards = list_product_cards(db, product_slug=product.slug)
        assert len(cards) == 1
        assert cards[0].lowest_price == Decimal("15.00")
        assert cards[0].related_lowest_price == Decimal("0.01")
        assert cards[0].trusted_offer_count == 2
        assert cards[0].median_price == Decimal("15.00")

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.lowest_price == Decimal("15.00")
        assert detail.related_lowest_price == Decimal("0.01")
        assert detail.trusted_offer_count == 2
        assert detail.offer_groups[0].lowest_price == Decimal("15.00")
        assert detail.offer_groups[0].representative.price == Decimal("15.00")


def test_catalog_aggregates_and_filters_do_not_mix_currencies():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        product = Product(slug="mixed-currency", platform="OpenAI", display_name="Mixed currency")
        db.add(product)
        db.flush()
        for token, price, currency in (
            ("cny-shop", Decimal("100"), "CNY"),
            ("usd-shop", Decimal("1"), "USD"),
        ):
            shop = Shop(token=token, name=token, source_url=f"https://example.com/{token}")
            db.add(shop)
            db.flush()
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=token,
                original_name="Same product",
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
                currency=currency,
                stock_status="in_stock",
                delivery_type="finished_account",
                is_comparable=True,
                item_fingerprint="same-fingerprint",
                source_url=shop.source_url,
                observed_at=now,
            )
            db.add(offer)
            db.flush()
            db.add(OfferHistory(
                offer_id=offer.id,
                price=price,
                currency=currency,
                stock_status="in_stock",
                observed_at=now,
            ))
        db.commit()

        card = list_product_cards(db, product_slug=product.slug)[0]
        assert card.price_currency == "CNY"
        assert card.lowest_price == Decimal("100.00")
        assert card.related_lowest_price == Decimal("100.00")

        detail = get_product_detail(db, product.slug)
        assert detail is not None
        assert detail.price_currency == "CNY"
        assert detail.lowest_price == Decimal("100.00")
        assert detail.related_lowest_price == Decimal("100.00")
        assert detail.offer_groups[0].price_currency == "CNY"
        assert detail.offer_groups[0].lowest_price == Decimal("100.00")
        assert detail.trend[-1].trusted_lowest_price == Decimal("100.00")

        groups, _, offer_total = get_product_group_page(
            db,
            product.id,
            offset=0,
            limit=30,
            filters=OfferFilters(min_price=Decimal("50")),
        )
        assert offer_total == 1
        assert groups[0].representative.currency == "CNY"

        usd_offers = get_group_offers(db, product.slug, "same-fingerprint", currency="USD")
        assert usd_offers is not None
        assert [(offer.currency, offer.price) for offer in usd_offers] == [("USD", Decimal("1.00"))]
