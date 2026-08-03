from __future__ import annotations

import json

from price_radar_http import PinnedResponse

from qualify import qualify_candidate


class FakeClient:
    normalize_url = staticmethod(__import__("price_radar_http").PinnedHTTPSClient.normalize_url)

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, *, accept: str) -> PinnedResponse:
        self.calls.append(url)
        handler = self.routes.get(url)
        if handler is None:
            raise ValueError("unexpected URL")
        return handler(url, accept)


def _json_route(payload, *, status=200, content_type="application/json"):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def handler(_url, _accept):
        return PinnedResponse(status, {"content-type": content_type}, body)

    return handler


def _html_route(body: bytes):
    def handler(_url, _accept):
        return PinnedResponse(200, {"content-type": "text/html"}, body)

    return handler


def test_woocommerce_purchasable_ai_product_is_detected():
    origin = "https://woo.example.com"
    products = [{
        "id": 1,
        "name": "ChatGPT Plus 1 month",
        "slug": "chatgpt-plus",
        "permalink": f"{origin}/product/chatgpt-plus",
        "is_purchasable": True,
        "is_in_stock": True,
        "prices": {"price": "8800", "regular_price": "8800", "currency_code": "CNY", "currency_minor_unit": 2},
    }]
    client = FakeClient({
        f"{origin}/api/v1/public/config": _json_route({"status_code": 1}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route({"status_code": 1}),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(products),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _json_route(
            products,
            content_type="application/json; charset=utf-8",
        ),
    })
    result = qualify_candidate(f"{origin}/products/chatgpt-plus", "unknown", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "woocommerce"
    assert result.detected_source_url == origin
    assert result.ai_product_count == 1
    assert result.sample_products[0]["name"] == "ChatGPT Plus 1 month"
    assert result.sample_products[0]["url"] == f"{origin}/product/chatgpt-plus"


def test_woocommerce_non_purchasable_products_do_not_qualify():
    origin = "https://woo.example.com"
    products = [{
        "id": 2,
        "name": "ChatGPT Plus 1 month",
        "slug": "chatgpt-plus",
        "permalink": f"{origin}/product/chatgpt-plus",
        "is_purchasable": False,
        "is_in_stock": True,
        "prices": {"price": "8800", "regular_price": "8800", "currency_code": "CNY", "currency_minor_unit": 2},
    }]
    client = FakeClient({
        f"{origin}/api/v1/public/config": _json_route({"status_code": 1}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route({"status_code": 1}),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(products),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _json_route(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0
    assert result.sample_products == []


def test_dujiao_product_api_qualifies_ai_product():
    origin = "https://dujiao.example.com"
    products = {
        "status_code": 0,
        "data": [
            {"slug": "chatgpt-plus", "title": {"zh-CN": "ChatGPT Plus 成品号"}},
            {"slug": "vpn", "title": {"zh-CN": "VPN 月卡"}},
        ],
        "pagination": {"page": 1, "page_size": 100, "total": 2, "total_page": 1},
    }
    client = FakeClient({
        f"{origin}/api/v1/public/config": _json_route({"status_code": 0, "data": {"brand": {"site_name": "Store"}}}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route(products),
        f"{origin}/api/v1/public/products?page=1&page_size=100": _json_route(products),
    })
    result = qualify_candidate(origin, "dujiao_next", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "dujiao_next"
    assert result.total_product_count == 2
    assert result.ai_product_count == 1
    assert result.sample_products[0]["product_slug"] == "chatgpt-plus"


def test_schema_org_product_page_qualifies_with_price_and_same_origin():
    origin = "https://structured.example.com"
    page = f"{origin}/products/chatgpt"
    body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Claude Pro 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "99", "priceCurrency": "CNY"}}
      }}</script>
    </head><body></body></html>""".encode("utf-8")
    client = FakeClient({
        f"{origin}/api/v1/public/config": _json_route({"status_code": 1}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route({"status_code": 1}),
        page: _html_route(body),
    })
    result = qualify_candidate(page, "schema_org", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "schema_org"
    assert result.detected_source_url == page
    assert result.ai_product_count == 1


def test_schema_org_missing_ai_products_is_no_match():
    origin = "https://ordinary.example.com"
    page = f"{origin}/products/ordinary"
    body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "普通鞋垫",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "19", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        f"{origin}/api/v1/public/config": _json_route({"status_code": 1}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route({"status_code": 1}),
        page: _html_route(body),
    })
    result = qualify_candidate(page, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0


def test_private_or_invalid_source_is_validation_failed():
    result = qualify_candidate("https://127.0.0.1/", "unknown", client=FakeClient({}))
    assert result.status == "validation_failed"
    assert result.ai_product_count == 0
