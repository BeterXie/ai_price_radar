from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.services.offer_classification import classify_offer
from common import Offer, Product, RawProduct, Shop, session_for
from publish_catalog import SourceSpec, publish_sources


@pytest.mark.parametrize("platform,title,category,raw,expected", [
    ("ldxp", "ChatGPT Plus 订阅成品账号", "GPT", {"description": "<p>账号密码交付</p><p>禁止共享和转卖</p>"}, "finished_account"),
    ("ldxp", "ChatGPT Plus 半成品账号", "GPT", {"description": "需要自行激活"}, "semi_finished_account"),
    ("16688", "PLUS 订阅 官方充值", "G直充", {"instruction": "充值到您自己的账号", "sourceCategory": {"name": "G直充"}}, "subscription_recharge"),
    ("ldxp", "Gemini Advanced 成品账号", "Gemini", {"description": "<p>3人共享账号</p>"}, "shared_pool"),
    ("ldxp", "ChatGPT Plus 成品/代充", "GPT", {}, "unknown"),
])
def test_full_refresh_and_admin_repair_keep_identical_delivery_fields(monkeypatch, tmp_path, platform, title, category, raw, expected):
    import export_snapshot
    import publish_catalog

    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "feed")
    record = {
        "token": "delivery-test", "shop_name": "Delivery test", "shop_url": "https://example.com",
        "source_platform": platform, "product_key": "delivery-offer", "product_name": title,
        "category_name": category, "raw_json": raw, "listed_price": "100",
        "stock_status": "in_stock", "product_url": "https://example.com/product",
    }
    monkeypatch.setattr(publish_catalog, "get_connector", lambda _name: lambda _source: iter([record]))
    with session_for("sqlite://") as db:
        for _ in range(2):
            publish_sources(db, [SourceSpec("ldxp", "test")])
            offer, product, stored_raw, shop = db.execute(
                select(Offer, Product, RawProduct, Shop)
                .join(Product, Offer.product_id == Product.id)
                .join(RawProduct, Offer.raw_product_id == RawProduct.id)
                .join(Shop, Offer.shop_id == Shop.id)
            ).one()
            repaired = classify_offer(SimpleNamespace(raw_product=stored_raw, shop=shop, price=offer.price))
            assert offer.delivery_type == repaired.delivery_type == expected
            assert product.slug == repaired.slug
            for field in ("is_comparable", "service_period", "warranty", "item_fingerprint", "use_scenarios", "tags", "risk_flags"):
                assert getattr(offer, field) == getattr(repaired, field), field
