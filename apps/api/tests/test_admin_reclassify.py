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
