import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from connectors import get_connector
from connectors import dujiao_next, merchant_json
from connectors.merchant_json import _validate_remote_url
from common import Offer, ensure_products, session_for, upsert_offer


def test_merchant_json_connector_normalizes_feed(tmp_path: Path):
    source = tmp_path / "feed.json"
    source.write_text(json.dumps({
        "shop": {"name": "Example merchant", "url": "https://merchant.example"},
        "updated_at": "2026-07-29T00:00:00+00:00",
        "items": [{
            "id": "plus-1",
            "name": "ChatGPT Plus 月卡",
            "url": "https://merchant.example/products/plus-1",
            "price": "99.00",
            "currency": "usd",
            "stock": 5,
            "stock_status": "in_stock",
            "auto_delivery": True,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    records = list(get_connector("merchant-json")(source))
    assert len(records) == 1
    record = records[0]
    assert record["source_platform"] == "merchant_json"
    assert record["product_name"] == "ChatGPT Plus 月卡"
    assert record["listed_price"] == "99.00"
    assert record["currency"] == "USD"
    assert record["stock_count"] == 5
    assert record["token"].startswith("feed-")


def test_dujiao_next_connector_paginates_and_emits_variants(monkeypatch):
    calls: list[str] = []
    client_ids: set[int] = set()

    def fake_get_json(url: str, **_kwargs):
        calls.append(url)
        client_ids.add(id(_kwargs["client"]))
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/v1/public/config":
            return {"status_code": 0, "msg": "success", "data": {"brand": {"site_name": "Example Dujiao"}, "currency": "usd"}}
        if parsed.path == "/api/v1/public/categories":
            return {"status_code": 0, "msg": "success", "data": [
                {"id": 10, "name": {"zh-CN": "订阅服务"}},
                {"id": 20, "name": {"en-US": "AI Accounts"}},
            ]}
        if parsed.path == "/api/v1/public/products":
            page = int(query["page"][0])
            products = {
                1: [{"slug": "vpn-subscription", "category_id": 10}],
                2: [{"slug": "chatgpt-plus", "category_id": 20}],
            }
            return {
                "status_code": 0,
                "msg": "success",
                "data": products[page],
                "pagination": {"page": page, "page_size": 100, "total": 2, "total_page": 2},
            }
        if parsed.path == "/api/v1/public/products/vpn-subscription":
            return {"status_code": 0, "msg": "success", "data": {
                "slug": "vpn-subscription",
                "category_id": 10,
                "title": {"zh-CN": "VPN 订阅", "en-US": "VPN subscription"},
                "content": {"zh-CN": "公开商品详情"},
                "fulfillment_type": "manual",
                "stock_status": "in_stock",
                "skus": [
                    {
                        "id": 11,
                        "sku_code": "STANDARD",
                        "spec_values": {"zh-CN": "标准版"},
                        "price_amount": "29.90",
                        "promotion_price_amount": "25.00",
                        "manual_stock_total": 10,
                        "manual_stock_sold": 3,
                        "auto_stock_available": 0,
                        "upstream_stock": 0,
                        "is_active": True,
                    },
                    {"id": 12, "sku_code": "DISABLED", "price_amount": "1.00", "is_active": False},
                ],
            }}
        if parsed.path == "/api/v1/public/products/chatgpt-plus":
            return {"status_code": 0, "msg": "success", "data": {
                "slug": "chatgpt-plus",
                "category_id": 20,
                "title": {"en-US": "ChatGPT Plus monthly"},
                "price_amount": "20.00",
                "fulfillment_type": "auto",
                "auto_stock_available": 4,
                "stock_status": "low_stock",
                "skus": [],
            }}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(dujiao_next, "_get_json", fake_get_json)
    monkeypatch.setattr(dujiao_next, "_validate_store_url", lambda value: urlsplit(value))

    records = list(get_connector("dujiao-next")("https://shop.example"))

    assert len(records) == 2
    variant, single = records
    assert variant["token"].startswith("dujiao-next-")
    assert variant["shop_name"] == "Example Dujiao"
    assert variant["source_platform"] == "dujiao_next"
    assert variant["product_key"] == "vpn-subscription:sku:11"
    assert variant["variant_key"] == "STANDARD"
    assert variant["product_name"] == "VPN 订阅 · 标准版"
    assert variant["product_url"] == "https://shop.example/products/vpn-subscription"
    assert variant["category_name"] == "订阅服务"
    assert variant["listed_price"] == "29.90"
    assert variant["currency"] == "USD"
    assert variant["stock_count"] == 7
    assert variant["product_status"] == "in_stock"
    assert variant["auto_delivery"] is False
    assert single["product_key"] == "chatgpt-plus"
    assert single["product_name"] == "ChatGPT Plus monthly"
    assert single["category_name"] == "AI Accounts"
    assert single["stock_count"] == 4
    assert any("page=2" in url for url in calls)
    assert len(client_ids) == 1

    db = session_for("sqlite://")
    try:
        upsert_offer(db, variant, ensure_products(db))
        assert db.query(Offer).one().auto_delivery is False
    finally:
        db.close()


def test_dujiao_next_connector_rejects_business_errors(monkeypatch):
    monkeypatch.setattr(dujiao_next, "_validate_store_url", lambda value: urlsplit(value))
    monkeypatch.setattr(
        dujiao_next,
        "_get_json",
        lambda url, **_kwargs: {"status_code": 503, "msg": "maintenance"},
    )

    with pytest.raises(ValueError, match="maintenance"):
        list(get_connector("dujiao-next")("https://shop.example"))


def test_dujiao_next_shop_name_supports_brand_overlay_and_fallbacks():
    assert dujiao_next._shop_name(
        {"brand": {"site_name": "Overlay Store"}, "site_name": "Base Store"},
        "shop.example",
    ) == "Overlay Store"
    assert dujiao_next._shop_name({"site_name": "Base Store"}, "shop.example") == "Base Store"
    assert dujiao_next._shop_name({"brand": {}}, "shop.example") == "shop.example"


def test_dujiao_next_connector_rejects_unsafe_shop_roots(monkeypatch):
    for value in (
        "http://shop.example",
        "https://127.0.0.1",
        "https://shop.example/api/v1/public/products",
        "https://shop.example?source=untrusted",
    ):
        with pytest.raises(ValueError):
            dujiao_next._validate_store_url(value)


def test_dujiao_next_connector_accepts_verified_empty_catalog(monkeypatch):
    def fake_get_json(url: str, **_kwargs):
        path = urlsplit(url).path
        if path == "/api/v1/public/config":
            return {"status_code": 0, "msg": "success", "data": {"site_name": "Empty shop", "currency": "CNY"}}
        if path == "/api/v1/public/categories":
            return {"status_code": 0, "msg": "success", "data": []}
        return {
            "status_code": 0,
            "msg": "success",
            "data": [],
            "pagination": {"page": 1, "page_size": 100, "total": 0, "total_page": 0},
        }

    monkeypatch.setattr(dujiao_next, "_get_json", fake_get_json)
    monkeypatch.setattr(dujiao_next, "_validate_store_url", lambda value: urlsplit(value))
    assert list(get_connector("dujiao-next")("https://empty.example")) == []


def test_connector_registry_rejects_unknown_connector():
    try:
        get_connector("missing")
    except ValueError as exc:
        assert "unknown connector" in str(exc)
    else:
        raise AssertionError("unknown connector should fail")


def test_merchant_connector_rejects_non_public_hosts():
    for value in ("http://example.com/feed.json", "https://localhost/feed.json", "https://127.0.0.1/feed.json"):
        try:
            _validate_remote_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe URL should fail: {value}")


def test_remote_connectors_read_through_the_pinned_https_client(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeClient:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **_kwargs):
            pass

        def get(self, url: str, *, accept: str):
            calls.append((url, accept))
            if "dujiao" in url:
                payload = {"status_code": 0, "data": {"brand": {"site_name": "Pinned"}}}
            else:
                payload = {
                    "shop": {"name": "Pinned feed", "url": "https://merchant.example"},
                    "items": [{
                        "id": "plus",
                        "name": "ChatGPT Plus monthly",
                        "url": "https://merchant.example/products/plus",
                    }],
                }
            return PinnedResponse(
                200,
                {"content-type": "application/json"},
                json.dumps(payload).encode(),
            )

    dujiao_document = dujiao_next._get_json("https://dujiao.example/api/v1/public/config", client=FakeClient())
    assert dujiao_document["data"]["brand"]["site_name"] == "Pinned"

    monkeypatch.setattr(merchant_json, "PinnedHTTPSClient", FakeClient)
    records = list(merchant_json.load_records("https://feed.example/catalog.json"))
    assert len(records) == 1
    assert records[0]["shop_name"] == "Pinned feed"
    assert calls == [
        ("https://dujiao.example/api/v1/public/config", "application/json"),
        ("https://feed.example/catalog.json", "application/json"),
    ]
