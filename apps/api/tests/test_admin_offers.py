from decimal import Decimal
from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, Product, RawProduct, Shop
from app.routers.admin import offers


def test_admin_offers_includes_stock_count_and_filters_stock_status():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(
            slug="chatgpt-plus",
            platform="OpenAI",
            display_name="ChatGPT Plus",
        )
        shop = Shop(token="TEST-SHOP", name="Test Shop", source_url="https://example.com", platform="ldxp")
        db.add_all([product, shop])
        db.flush()

        raw1 = RawProduct(
            shop_id=shop.id,
            source_product_key="k1",
            original_name="GPT Plus In Stock",
            original_category="Plus",
        )
        raw2 = RawProduct(
            shop_id=shop.id,
            source_product_key="k2",
            original_name="GPT Plus Out Of Stock",
            original_category="Plus",
        )
        db.add_all([raw1, raw2])
        db.flush()

        offer1 = Offer(
            raw_product_id=raw1.id,
            product_id=product.id,
            shop_id=shop.id,
            price=Decimal("88.00"),
            currency="CNY",
            stock_count=42,
            stock_status="in_stock",
            approved=True,
            active=True,
        )
        offer2 = Offer(
            raw_product_id=raw2.id,
            product_id=product.id,
            shop_id=shop.id,
            price=Decimal("85.00"),
            currency="CNY",
            stock_count=0,
            stock_status="out_of_stock",
            approved=True,
            active=True,
        )
        db.add_all([offer1, offer2])
        db.commit()

        # Query all
        res_all = offers(response=Response(), db=db)
        assert len(res_all) == 2
        o1 = next(x for x in res_all if x["id"] == offer1.id)
        assert o1["stock_count"] == 42
        assert o1["stock_status"] == "in_stock"

        o2 = next(x for x in res_all if x["id"] == offer2.id)
        assert o2["stock_count"] == 0
        assert o2["stock_status"] == "out_of_stock"

        # Filter in_stock
        res_in_stock = offers(stock_status="in_stock", response=Response(), db=db)
        assert len(res_in_stock) == 1
        assert res_in_stock[0]["id"] == offer1.id
        assert res_in_stock[0]["stock_count"] == 42

        # Filter out_of_stock
        res_out = offers(stock_status="out_of_stock", response=Response(), db=db)
        assert len(res_out) == 1
        assert res_out[0]["id"] == offer2.id
        assert res_out[0]["stock_count"] == 0
