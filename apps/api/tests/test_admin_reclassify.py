from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Offer, Product, RawProduct, Shop
from app.routers.admin import reclassify
import pytest


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


@pytest.mark.parametrize("source", ["ldxp", "16688"])
def test_historical_plan_repair_is_previewable_and_preserves_manual_decisions(source, monkeypatch):
    from pathlib import Path
    from sqlalchemy import select
    from app.services.account_plans import ensure_account_plans

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))
    from scripts.reclassify_account_offers import preview

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ensure_account_plans(db)
        old_pro = db.scalar(select(Product).where(Product.slug == "chatgpt-pro-20x"))
        shop = Shop(token="REPAIR", name="Test", platform=source, source_url="https://example.com")
        db.add(shop)
        db.flush()
        cases = [
            ("Business / Team 标准席位续费码", "不是5Xteam", "chatgpt-business", []),
            ("Perplexity Max 自助充值月卡", "200刀/月（支持Claude模型）", None, []),
            ("ChatGPT Pro 200刀月卡", "", "chatgpt-pro-200", []),
            ("Muse成品号+10亿token", "支持GPT", "muse-account", []),
            ("JEV 成品账号", "", "jev-account", []),
            ("JEV 成品账号", "", "chatgpt-pro-200", ["manual_override"]),
        ]
        offers = []
        for index, (title, description, expected, tags) in enumerate(cases):
            raw = RawProduct(shop_id=shop.id, source_product_key=str(index), original_name=title, raw_json={"description": description})
            db.add(raw)
            db.flush()
            offer = Offer(raw_product_id=raw.id, shop_id=shop.id, product_id=None if index == 4 else old_pro.id, active=True, approved=index != 4, tags=tags)
            db.add(offer)
            offers.append(offer)
        db.commit()
        before = [(offer.product_id, offer.approved, offer.item_fingerprint) for offer in offers]
        report = preview(db)
        assert report["changed"] == 5
        assert report["manual_skipped"] == 1
        assert before == [(offer.product_id, offer.approved, offer.item_fingerprint) for offer in offers]
        assert not db.dirty
        result = reclassify(db)
        # The old Pro identity is merged before reclassification; the already
        # correct Pro 200 SKU therefore needs no additional classification edit.
        assert result["changed"] == 4
        for offer, (_, _, expected, _) in zip(offers, cases):
            db.refresh(offer)
            target = db.get(Product, offer.product_id) if offer.product_id else None
            assert (target.slug if target else None) == expected
        assert offers[4].approved
        assert reclassify(db)["changed"] == 0
    engine.dispose()


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


def test_update_offer_manual_reclassify_and_unclassify():
    from app.routers.admin import update_offer
    from app.schemas import AdminOfferUpdate

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        plus = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        pro = Product(slug="chatgpt-pro", platform="OpenAI", display_name="ChatGPT Pro")
        shop = Shop(token="S1", name="Shop1", source_url="https://example.com")
        db.add_all([plus, pro, shop])
        db.flush()
        raw = RawProduct(shop_id=shop.id, source_product_key="P1", original_name="Plus", original_category="Category")
        db.add(raw)
        db.flush()
        offer = Offer(raw_product_id=raw.id, product_id=plus.id, shop_id=shop.id, active=True)
        db.add(offer)
        db.commit()

        # Reclassify to pro
        update_offer(offer.id, AdminOfferUpdate(product_slug="chatgpt-pro"), db)
        db.refresh(offer)
        assert offer.product_id == pro.id

        # Unclassify
        update_offer(offer.id, AdminOfferUpdate(product_slug=""), db)
        db.refresh(offer)
        assert offer.product_id is None
        assert "manual_override" in offer.tags
        assert offer.classification_confidence == 100

        # Full automatic reclassification must preserve the explicit removal.
        reclassify(db)
        db.refresh(offer)
        assert offer.product_id is None


def test_reclassify_single_offer_and_status_filtering():
    from app.routers.admin import offers, reclassify_offer

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        plus = Product(slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus")
        shop = Shop(token="TEST", name="TestShop", source_url="https://example.com")
        db.add_all([plus, shop])
        db.flush()
        raw1 = RawProduct(shop_id=shop.id, source_product_key="K1", original_name="ChatGPT Plus 成品", original_category="GPT")
        raw2 = RawProduct(shop_id=shop.id, source_product_key="K2", original_name="Nume API 10$ plus分组", original_category="API")
        db.add_all([raw1, raw2])
        db.flush()
        offer1 = Offer(raw_product_id=raw1.id, product_id=None, shop_id=shop.id, active=True, approved=True)
        offer2 = Offer(raw_product_id=raw2.id, product_id=None, shop_id=shop.id, active=False, hidden_reason="不属于 OpenAI Plus 账号")
        db.add_all([offer1, offer2])
        db.commit()

        # Single offer reclassify
        res = reclassify_offer(offer1.id, db)
        assert res["ok"] is True
        assert res["product_slug"] == "chatgpt-plus"
        db.refresh(offer1)
        assert offer1.product_id == plus.id

        # Status filtering: restricted
        restricted = offers(status="restricted", db=db)
        assert len(restricted) == 1
        assert restricted[0]["id"] == offer2.id
        assert "不属于 OpenAI Plus 账号" in restricted[0]["hidden_reason"]

        # Status filtering: unclassified
        unclassified = offers(status="unclassified", db=db)
        assert len(unclassified) == 1
        assert unclassified[0]["id"] == offer2.id

        # Search filtering by title
        searched = offers(q="Nume", db=db)
        assert len(searched) == 1
        assert searched[0]["id"] == offer2.id

        # Brand filtering
        openai_offers = offers(brand="OpenAI", db=db)
        assert len(openai_offers) == 1
        assert openai_offers[0]["id"] == offer1.id
        assert openai_offers[0]["brand"] == "OpenAI"
        assert openai_offers[0]["product_name"] == "ChatGPT Plus"

        # Total count header & sorting
        from fastapi import Response
        from app.routers.admin import stats
        resp = Response()
        sorted_offers = offers(sort="frontend", response=resp, db=db)
        assert len(sorted_offers) == 2
        assert resp.headers["X-Total-Count"] == "2"

        # Stats returns product_counts & brand_counts
        current_stats = stats(db=db)
        assert current_stats.product_counts.get("chatgpt-plus") == 1
        assert current_stats.brand_counts.get("OpenAI") == 1
