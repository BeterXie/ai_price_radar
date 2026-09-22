from __future__ import annotations

import json
from decimal import Decimal

import pytest
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from connectors import acg_faka


class FakeClient:
    normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

    def __init__(self, **_kwargs):
        pass

    def get(self, url: str, *, accept: str | None = None) -> PinnedResponse:
        if url == "https://shop.example.com":
            return PinnedResponse(
                status=200,
                headers={"content-type": "text/html; charset=utf-8"},
                body=b"<html><head><title>\xe8\xb4\xad\xe7\x89\xa9 - \xe4\xb8\x80\xe7\xab\x99\xe5\xbc\x8f AI \xe6\x9d\x82\xe8\xb4\xa7\xe9\x93\xba</title></head></html>",
            )
        if url == "https://shop.example.com/user/api/index/data":
            return PinnedResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps({
                    "code": 200,
                    "msg": "success",
                    "data": [
                        {"id": 11, "name": "ChatGPT", "commodity_count": 2},
                        {"id": 14, "name": "Claude", "commodity_count": 1},
                    ],
                }).encode("utf-8"),
            )
        if url == "https://shop.example.com/user/api/index/commodity":
            return PinnedResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps({
                    "code": 200,
                    "msg": "success",
                    "data": [
                        {
                            "id": 101,
                            "name": "ChatGPT Plus 月付订阅",
                            "price": "125.00",
                            "stock": 50,
                            "status": 1,
                            "delivery_way": 0,
                            "category_id": 11,
                            "hide": 0,
                        },
                        {
                            "id": 102,
                            "name": "Claude Pro 独立号",
                            "price": "130.00",
                            "stock": 0,
                            "status": 1,
                            "delivery_way": 0,
                            "category_id": 14,
                            "hide": 0,
                        },
                        {
                            "id": 103,
                            "name": "下架商品",
                            "price": "99.00",
                            "stock": 10,
                            "status": 0,
                            "delivery_way": 1,
                            "category_id": 11,
                            "hide": 0,
                        },
                    ],
                }).encode("utf-8"),
            )
        return PinnedResponse(status=404, headers={}, body=b"not found")


def test_acg_faka_url_validation():
    assert acg_faka._validate_store_url("https://shop.example.com").netloc == "shop.example.com"
    assert acg_faka._validate_store_url("https://shop.example.com/").netloc == "shop.example.com"

    with pytest.raises(ValueError, match="shop root URL"):
        acg_faka._validate_store_url("https://shop.example.com/item/1")

    with pytest.raises(ValueError, match="shop root URL"):
        acg_faka._validate_store_url("https://shop.example.com/?query=1")


def test_acg_faka_load_records(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(acg_faka, "PinnedHTTPSClient", FakeClient)

    records = list(acg_faka.load_records("https://shop.example.com"))
    assert len(records) == 3

    r1 = records[0]
    assert r1["source_platform"] == "acg_faka"
    assert r1["source_kind"] == "public_api"
    assert r1["shop_name"] == "一站式 AI 杂货铺"
    assert r1["shop_url"] == "https://shop.example.com"
    assert r1["product_key"] == "101"
    assert r1["product_name"] == "ChatGPT Plus 月付订阅"
    assert r1["category_name"] == "ChatGPT"
    assert r1["product_url"] == "https://shop.example.com/item/101"
    assert r1["listed_price"] == Decimal("125.00")
    assert r1["currency"] == "CNY"
    assert r1["stock_count"] == 50
    assert r1["product_status"] == "in_stock"
    assert r1["auto_delivery"] is True

    # Out of stock item
    r2 = records[1]
    assert r2["product_key"] == "102"
    assert r2["category_name"] == "Claude"
    assert r2["stock_count"] == 0
    assert r2["product_status"] == "out_of_stock"

    # Disabled item
    r3 = records[2]
    assert r3["product_key"] == "103"
    assert r3["product_status"] == "unavailable"
    assert r3["auto_delivery"] is False
