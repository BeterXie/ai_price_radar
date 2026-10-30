from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from common import Offer, OfferHistory, Product, RawProduct, session_for
from app.services.offer_classification import classify_offer
from connectors import platform_16688
from connectors.base import SourceFetchError
from publish_catalog import SourceSpec, publish_sources


SHOP_URL = "https://www.16688.com.cn/shop/S878919"
CATEGORY = {"goods_category_no": "C698563", "name": "G直充"}
# Public titles/IDs captured from S878919; unrelated HTML is omitted.
GOODS = [
    ("G40240306", "IOS 【质保30天】 PLUS 订阅 官方充值 免排队 秒充(1-10分钟到账)（可屯卡）", 135, -1),
    ("G30720814", "【美区IOS】质保30天（可覆盖）G pro5x 订阅 官方充值 免排队 秒充(5-10分钟到账)", 580, 11),
    ("G96954851", "【美区IOS】质保30天（可覆盖）G pro 20x 订阅 官方充值 免排队 秒充(5-10分钟到账)", 1250, -1),
    ("G65523543", "ios正规plus年卡全程质保", 1250, -1),
]
EXPECTED_SLUGS = ["chatgpt-plus", "chatgpt-pro-5x", "chatgpt-pro-20x", "chatgpt-plus"]


@pytest.fixture
def source_api(monkeypatch, tmp_path):
    import export_snapshot

    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "feed")
    state = {
        "calls": [],
        "categories": [
            {"goods_category_no": "COTHER", "name": "Claude"},
            dict(CATEGORY),
        ],
        "category_status": 200,
        "items": [
            {
                "goods_no": code, "name": title, "price": price,
                "goods_category_no": CATEGORY["goods_category_no"],
                "stock_available_quantity": stock,
                "description": "自助充值到自己账号；若加入过 Team 空间，请先切回个人版再获取 Token。",
            }
            for code, title, price, stock in GOODS
        ],
    }

    class FakeClient:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **_kwargs):
            pass

        def post_json(self, url, payload):
            state["calls"].append((url, payload))
            status = 200
            if url.endswith(platform_16688.SHOP_DETAIL_PATH):
                data = {"shop_no": "S878919", "name": "Source shop"}
            elif url.endswith(platform_16688.GOODS_DETAIL_PATH):
                data = {"shop_no": "S878919", "goods_no": payload["goods_no"]}
            elif url.endswith(platform_16688.GOODS_LIST_PATH):
                data = {"list": state["items"]}
            elif url.endswith(platform_16688.GOODS_CATEGORY_LIST_PATH):
                assert payload == {"shop_no": "S878919"}
                data = state["categories"]
                status = state["category_status"]
            else:
                pytest.fail(f"unexpected request: {url}")
            return PinnedResponse(status, {"content-type": "application/json"}, json.dumps({"code": 1, "data": data}).encode())

    monkeypatch.setattr(platform_16688, "PinnedHTTPSClient", FakeClient)
    return state


@pytest.mark.parametrize("source", [SHOP_URL, "https://www.16688.com.cn/shop/ALIAS", "https://www.16688.com.cn/goods/G40240306"])
def test_categories_are_joined_by_id_after_canonical_shop_resolution(source_api, source):
    records = list(platform_16688.load_records(source))
    assert len(records) == 4
    assert [r["product_key"] for r in records] == [f"16688:{item[0]}" for item in GOODS]
    assert [r["listed_price"] for r in records] == [item[2] for item in GOODS]
    assert all(r["shop_url"] == SHOP_URL and r["category_name"] == "G直充" for r in records)
    assert [r["raw_json"]["goods_category_no"] for r in records] == ["C698563"] * 4
    assert all("sourceCategory" not in item for item in source_api["items"])
    category_calls = [call for call in source_api["calls"] if call[0].endswith(platform_16688.GOODS_CATEGORY_LIST_PATH)]
    assert len(category_calls) == 1


def test_missing_and_unknown_category_ids_do_not_borrow_a_shop_category(source_api):
    del source_api["items"][0]["goods_category_no"]
    source_api["items"][3]["goods_category_no"] = "UNKNOWN"
    source_api["items"][3]["sourceCategory"] = {"name": "Original source category"}
    records = list(platform_16688.load_records(SHOP_URL))
    assert [r["category_name"] for r in records] == ["", "G直充", "G直充", ""]
    assert records[3]["raw_json"]["sourceCategory"] == {"name": "Original source category"}


def test_empty_category_list_keeps_all_goods(source_api):
    source_api["categories"] = []
    records = list(platform_16688.load_records(SHOP_URL))
    assert len(records) == 4
    assert all(r["category_name"] == "" for r in records)


def test_no_category_ids_avoids_an_unneeded_category_request(source_api):
    for item in source_api["items"]:
        del item["goods_category_no"]
    assert len(list(platform_16688.load_records(SHOP_URL))) == 4
    assert not any(url.endswith(platform_16688.GOODS_CATEGORY_LIST_PATH) for url, _ in source_api["calls"])


@pytest.mark.parametrize("categories", [None, {}, [None], [{}], [{"goods_category_no": "C1"}], [CATEGORY, CATEGORY]])
def test_malformed_category_data_is_not_treated_as_a_successful_empty_catalog(source_api, categories):
    source_api["categories"] = categories
    with pytest.raises(ValueError, match="16688 category"):
        list(platform_16688.load_records(SHOP_URL))


def test_category_fetch_failure_remains_a_source_fetch_error(source_api):
    source_api["category_status"] = 503
    with pytest.raises(SourceFetchError, match="HTTP 503"):
        list(platform_16688.load_records(SHOP_URL))


@pytest.mark.parametrize("category_field", ["sourceCategory", "source_category"])
def test_existing_source_category_metadata_coexists_with_mapped_category(source_api, category_field):
    for item in source_api["items"]:
        item[category_field] = dict(CATEGORY)
    records = list(platform_16688.load_records(SHOP_URL))
    assert [r["category_name"] for r in records] == ["G直充"] * 4
    assert all(r["raw_json"][category_field] == CATEGORY for r in records)
    db = session_for("sqlite://")
    try:
        result = publish_sources(db, [SourceSpec("16688", SHOP_URL)])
        assert result.imports[0].public_offer_count == 4
        rows = (
            db.query(Offer, RawProduct, Product)
            .join(RawProduct, Offer.raw_product_id == RawProduct.id)
            .join(Product, Offer.product_id == Product.id)
            .order_by(Offer.id).all()
        )
        assert [product.slug for _, _, product in rows] == EXPECTED_SLUGS
        for offer, raw, product in rows:
            classified = classify_offer(SimpleNamespace(
                raw_product=raw, shop=SimpleNamespace(platform="16688"), price=offer.price,
            ))
            assert classified.slug == product.slug
    finally:
        db.close()


@pytest.mark.parametrize("hide_annual", [False, True])
def test_sync_recovers_unclassified_plus_without_duplicates_or_unhiding_manual_decisions(source_api, hide_annual):
    db = session_for("sqlite://")
    try:
        source_api["categories"] = []
        initial = publish_sources(db, [SourceSpec("16688", SHOP_URL)])
        assert (initial.imports[0].raw_record_count, initial.imports[0].public_offer_count) == (4, 2)
        initial_ids = [offer.id for offer in db.query(Offer).order_by(Offer.id)]
        if hide_annual:
            annual = db.query(Offer).join(RawProduct).filter(RawProduct.source_product_key == "16688:G65523543").one()
            annual.hidden_reason = "manual moderation"
            db.commit()

        source_api["categories"] = [dict(CATEGORY)]
        recovered = publish_sources(db, [SourceSpec("16688", SHOP_URL)])
        imported = recovered.imports[0]
        assert (imported.raw_record_count, imported.classified_offer_count, imported.public_offer_count) == (4, 4, 3 if hide_annual else 4)
        rows = db.query(Offer, RawProduct, Product).join(RawProduct, Offer.raw_product_id == RawProduct.id).join(Product, Offer.product_id == Product.id).order_by(Offer.id).all()
        assert [offer.id for offer, _, _ in rows] == initial_ids
        assert [product.slug for _, _, product in rows] == EXPECTED_SLUGS
        assert all(raw.original_category == "G直充" for _, raw, _ in rows)
        assert [offer.approved for offer, _, _ in rows] == [True, True, True, not hide_annual]
        assert all(offer.stock_status == "in_stock" for offer, _, _ in rows)
        # Admin reclassification consumes the persisted category too.
        for offer, raw, product in rows:
            classified = classify_offer(SimpleNamespace(raw_product=raw, shop=SimpleNamespace(platform="16688"), price=offer.price))
            assert classified.slug == product.slug
        assert db.query(RawProduct).count() == db.query(Offer).count() == db.query(OfferHistory).count() == 4
        repeated = publish_sources(db, [SourceSpec("16688", SHOP_URL)])
        assert repeated.offer_count == 4
        assert repeated.imports[0].public_offer_count == (3 if hide_annual else 4)
        assert [offer.approved for offer in db.query(Offer).order_by(Offer.id)] == [True, True, True, not hide_annual]
        assert db.query(Offer).count() == db.query(OfferHistory).count() == 4
    finally:
        db.close()
