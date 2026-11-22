"""Exercise collection-shaped records through publication and public filtering."""
import json
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from common import Offer, begin_snapshot, ensure_products, session_for, upsert_offer, utcnow
from export_snapshot import export_public_snapshot
from app.services.catalog import OfferFilters, get_catalog_group_page, get_product_detail
from app.services.snapshot_catalog import QuoteQuery, SnapshotCatalog


CASES = [
    ("email-gmail", "邮箱", "Gmail 老号 独享", "finished_account"),
    ("verification-claude", "接码 / 验证", "Claude 自助接码", "verification_service"),
    ("virtual-card", "虚拟卡", "VISA 虚拟卡", "virtual_card"),
    ("gift-card", "礼品卡", "Apple 礼品卡 10美元 美区", "gift_card"),
    ("social-media-account", "社媒账号", "Discord 成品账号 已接码 附Outlook邮箱", "finished_account"),
    ("apple-id-account", "Apple ID", "Apple ID 美区独享账号", "finished_account"),
    ("vps", "VPS", "香港 VPS 2核4G 年付", "hosting_service"),
    ("chatgpt-plus", "OpenAI", "ChatGPT Plus 官方直充 1个月", "subscription_recharge"),
]


@pytest.mark.parametrize("source", ["ldxp", "16688", "merchant_json"])
def test_auxiliary_quotes_reach_snapshot_and_public_catalog(tmp_path, source):
    with session_for("sqlite://") as db:
        products = ensure_products(db)
        snapshot = begin_snapshot(db, "auxiliary-test")
        for index, (slug, category, title, delivery) in enumerate(CASES):
            record = {
                "token": "aux-test", "shop_name": "辅助商品测试店",
                "shop_url": "https://example.com/shop", "source_platform": source,
                "product_key": slug, "product_name": title, "category_name": category,
                "listed_price": str(10 + index), "stock_count": 3,
                "product_status": "有货", "observed_at": utcnow(),
                "product_url": f"https://example.com/items/{slug}",
            }
            upsert_offer(db, record, products, snapshot.id)
            upsert_offer(db, record, products, snapshot.id)
            offer = db.query(Offer).filter_by(product_id=products[slug].id).one()
            assert offer.approved and offer.is_comparable
            assert offer.delivery_type == delivery
        snapshot.published_at = utcnow()
        snapshot.offer_count = len(CASES)
        db.commit()
        assert db.query(Offer).count() == len(CASES)

        export_public_snapshot(db, snapshot_id=snapshot.id, output_dir=tmp_path)
        data = json.loads((tmp_path / "v1" / "snapshots" / f"{snapshot.id}.json").read_text(encoding="utf-8"))
        catalog = SnapshotCatalog(data)
        # Check the API grouping/detail path against imported data as well.
        with Session(db.get_bind()) as public_db:
            for index, (slug, category, title, delivery) in enumerate(CASES):
                rows = catalog.search(QuoteQuery(brand=category))
                assert [row[0]["slug"] for row in rows] == [slug]
                assert rows[0][1]["delivery_type"] == delivery
                groups, total, *_ = get_catalog_group_page(
                    public_db, platform=category, offset=0, limit=30,
                    filters=OfferFilters(comparable=True),
                )
                assert total == 1 and groups[0].product_slug == slug
                detail = get_product_detail(public_db, slug)
                assert detail.offer_count == 1
                assert detail.lowest_price == Decimal(10 + index)
                assert detail.offer_groups[0].representative.original_name == title


@pytest.mark.parametrize("locked", ["manual", "hidden", "unclassified"])
def test_new_category_import_respects_existing_moderation(locked):
    with session_for("sqlite://") as db:
        products = ensure_products(db)
        record = {
            "token": "moderated-aux", "product_key": "mail",
            "product_name": "Gmail 邮箱", "source_platform": "ldxp", "price": "5.00",
        }
        upsert_offer(db, record, products)
        offer = db.query(Offer).one()
        original_id = offer.id
        offer.product_id = None
        offer.approved = False
        if locked == "manual":
            offer.tags = ["manual_override"]
        elif locked == "hidden":
            offer.hidden_reason = "人工隐藏"
        db.commit()
        upsert_offer(db, record, products)
        db.flush()
        assert offer.id == original_id
        if locked == "manual":
            assert offer.product_id is None and not offer.approved
        elif locked == "hidden":
            assert offer.hidden_reason == "人工隐藏" and not offer.approved
        else:
            assert offer.product_id == products["email-gmail"].id and offer.approved
