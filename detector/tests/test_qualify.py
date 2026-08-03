from __future__ import annotations

import json

import pytest
from price_radar_http import PinnedResponse

from qualify import qualify_candidate


class FakeClient:
    normalize_url = staticmethod(__import__("price_radar_http").PinnedHTTPSClient.normalize_url)

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, *, accept: str) -> PinnedResponse:
        url = self.normalize_url(url)
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


def _xml_route(body: bytes):
    def handler(_url, _accept):
        return PinnedResponse(200, {"content-type": "application/xml"}, body)

    return handler


def _probe_routes(origin: str):
    return {
        f"{origin}/api/v1/public/config": _json_route({"status_code": 1}),
        f"{origin}/api/v1/public/products?page=1&page_size=1": _json_route({"status_code": 1}),
    }


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


@pytest.mark.parametrize("bad_prices", [
    {"price": "abc", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "NaN", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "Infinity", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "-1", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "100", "currency_code": "", "currency_minor_unit": 2},
    {"price": "100", "currency_code": "CNY", "currency_minor_unit": -1},
    {"price": "100", "currency_code": "CNY", "currency_minor_unit": "2"},
    {"price": True, "currency_code": "CNY", "currency_minor_unit": 2},
])
def test_woocommerce_invalid_prices_are_not_qualified(bad_prices):
    origin = "https://woo-price.example.com"
    products = [{
        "id": 3,
        "name": "ChatGPT Plus 1 month",
        "slug": "chatgpt-plus",
        "permalink": f"{origin}/product/chatgpt-plus",
        "is_purchasable": True,
        "is_in_stock": True,
        "prices": bad_prices,
    }]
    client = FakeClient({
        **_probe_routes(origin),
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


@pytest.mark.parametrize("bad_price", ["contact us", "NaN", "Infinity", "-1"])
def test_schema_org_invalid_prices_are_not_qualified(bad_price):
    origin = "https://structured-price.example.com"
    page = f"{origin}/products/chatgpt"
    body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "ChatGPT Plus 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "{bad_price}", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        page: _html_route(body),
    })
    result = qualify_candidate(page, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0


def test_schema_org_mixed_currency_aggregate_offer_is_not_qualified():
    origin = "https://structured-mixed.example.com"
    page = f"{origin}/products/chatgpt"
    body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "ChatGPT Plus 月卡",
        "url": "{page}",
        "offers": [{{
          "@type": "AggregateOffer",
          "lowPrice": "100",
          "highPrice": "110",
          "priceCurrency": "CNY"
        }}, {{"@type": "Offer", "price": "15", "priceCurrency": "USD"}}]
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        page: _html_route(body),
    })
    result = qualify_candidate(page, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0


def test_schema_org_root_entry_is_preserved_when_default_sitemap_is_used():
    origin = "https://root-schema.example.com"
    page = f"{origin}/products/chatgpt"
    root_body = b"<html><head></head><body>no products here</body></html>"
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{page}</loc></url>
    </urlset>""".encode("utf-8")
    product_body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Claude Pro 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "99", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        f"{origin}/": _html_route(root_body),
        f"{origin}/sitemap.xml": _xml_route(sitemap),
        page: _html_route(product_body),
    })
    result = qualify_candidate(origin, "schema_org", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "schema_org"
    assert result.detected_source_url.rstrip("/") == origin
    assert result.detected_source_key.rstrip("/") == origin
    assert result.ai_product_count == 1


def test_schema_org_sitemap_index_recurses_into_child_sitemap():
    origin = "https://index-schema.example.com"
    index_url = f"{origin}/index.xml"
    child_url = f"{origin}/child-product-sitemap.xml"
    page = f"{origin}/products/chatgpt"
    index = f"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>{child_url}</loc></sitemap>
    </sitemapindex>""".encode("utf-8")
    child = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{page}</loc></url>
    </urlset>""".encode("utf-8")
    product_body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Gemini Advanced 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "120", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        index_url: _xml_route(index),
        child_url: _xml_route(child),
        page: _html_route(product_body),
    })
    result = qualify_candidate(index_url, "schema_org", client=client)
    assert result.status == "detected"
    assert result.detected_source_url == index_url
    assert result.ai_product_count == 1
    assert "schema-org-sitemap" in result.fingerprints


def test_schema_org_sitemap_index_depth_limit_fails_validation():
    origin = "https://depth-schema.example.com"
    entry = f"{origin}/index.xml"

    def make_index(target):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>{target}</loc></sitemap>
        </sitemapindex>""".encode("utf-8")

    routes = {
        **_probe_routes(origin),
        entry: _xml_route(make_index(f"{origin}/a.xml")),
        f"{origin}/a.xml": _xml_route(make_index(f"{origin}/b.xml")),
        f"{origin}/b.xml": _xml_route(make_index(f"{origin}/c.xml")),
        f"{origin}/c.xml": _xml_route(make_index(f"{origin}/d.xml")),
    }
    client = FakeClient(routes)
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "validation_failed"
    assert "recursion depth" in result.failure_reason


def test_schema_org_sitemap_count_limit_fails_validation():
    origin = "https://count-schema.example.com"
    entry = f"{origin}/index.xml"
    children = "\n".join(
        f"<sitemap><loc>{origin}/child-{index}.xml</loc></sitemap>" for index in range(33)
    )
    index = f"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      {children}
    </sitemapindex>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        entry: _xml_route(index),
    })
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "validation_failed"
    assert "sitemap count" in result.failure_reason


def test_schema_org_cross_origin_child_sitemap_is_ignored():
    origin = "https://cross-schema.example.com"
    entry = f"{origin}/index.xml"
    page = f"{origin}/products/chatgpt"
    index = f"""<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://evil.example/child.xml</loc></sitemap>
      <sitemap><loc>{origin}/child.xml</loc></sitemap>
    </sitemapindex>""".encode("utf-8")
    child = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{page}</loc></url>
    </urlset>""".encode("utf-8")
    product_body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Grok Super 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "80", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        entry: _xml_route(index),
        f"{origin}/child.xml": _xml_route(child),
        page: _html_route(product_body),
    })
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 1
    assert "evil.example" not in " ".join(client.calls)


def test_schema_org_dtd_entity_sitemap_fails_validation():
    origin = "https://dtd-schema.example.com"
    entry = f"{origin}/sitemap.xml"
    body = b"""<?xml version="1.0"?>
    <!DOCTYPE urlset [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>&xxe;</loc></url></urlset>"""
    client = FakeClient({
        **_probe_routes(origin),
        entry: _xml_route(body),
    })
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "validation_failed"
    assert "DTD" in result.failure_reason


def test_private_or_invalid_source_is_validation_failed():
    result = qualify_candidate("https://127.0.0.1/", "unknown", client=FakeClient({}))
    assert result.status == "validation_failed"
    assert result.ai_product_count == 0
