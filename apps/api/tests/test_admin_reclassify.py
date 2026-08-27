from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, Product, RawProduct, Shop
from app.routers.admin import reclassify


def test_reclassify_clears_an_invalid_previous_product():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(
            slug="chatgpt-plus",
            platform="ChatGPT",
            display_name="ChatGPT Plus",
        )
        shop = Shop(token="TEST", name="Test", source_url="https://example.invalid/shop")
        db.add_all([product, shop])
        db.flush()
        raw = RawProduct(
            shop_id=shop.id,
            source_product_key="gmail",
            original_name="Google Gmail 老号",
            original_category="谷歌账号",
        )
        db.add(raw)
        db.flush()
        offer = Offer(raw_product_id=raw.id, product_id=product.id, shop_id=shop.id)
        db.add(offer)
        db.commit()

        result = reclassify(db)

        db.refresh(offer)
        assert offer.product_id is None
        assert result == {"ok": True, "changed": 1, "unclassified": 1}


def test_reclassify_uses_16688_detail_fields():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(
            slug="chatgpt-plus",
            platform="OpenAI",
            display_name="ChatGPT Plus",
        )
        shop = Shop(token="16688-S1", name="16688", source_url="https://www.16688.com.cn/shop/S1", platform="16688")
        db.add_all([product, shop])
        db.flush()
        raw = RawProduct(
            shop_id=shop.id,
            source_product_key="G1",
            original_name="官方充值 Plus CDK",
            original_category="AI与效率",
            raw_json={
                "description": "商品内容：GP.T Plus 1个月",
                "instruction": "官方订阅充值",
                "sourceCategory": {"name": "AI与效率"},
            },
        )
        db.add(raw)
        db.flush()
        offer = Offer(raw_product_id=raw.id, product_id=None, shop_id=shop.id)
        db.add(offer)
        db.commit()

        result = reclassify(db)

        db.refresh(offer)
        assert offer.product_id == product.id
        assert offer.approved is True
        assert result == {"ok": True, "changed": 1, "unclassified": 0}


def test_reclassify_does_not_restore_a_manually_hidden_16688_offer():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(
            slug="chatgpt-plus",
            platform="OpenAI",
            display_name="ChatGPT Plus",
        )
        shop = Shop(
            token="16688-S2",
            name="16688",
            source_url="https://www.16688.com.cn/shop/S2",
            platform="16688",
        )
        db.add_all([product, shop])
        db.flush()
        raw = RawProduct(
            shop_id=shop.id,
            source_product_key="G2",
            original_name="官方充值 Plus CDK",
            original_category="AI与效率",
            raw_json={"description": "GP.T Plus 1个月"},
        )
        db.add(raw)
        db.flush()
        offer = Offer(
            raw_product_id=raw.id,
            product_id=None,
            shop_id=shop.id,
            approved=False,
            active=False,
            hidden_reason="manual moderation",
        )
        db.add(offer)
        db.commit()

        reclassify(db)

        db.refresh(offer)
        assert offer.product_id == product.id
        assert offer.approved is False
        assert offer.active is False
        assert offer.hidden_reason == "manual moderation"
