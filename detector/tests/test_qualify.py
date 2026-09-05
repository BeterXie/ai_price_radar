from __future__ import annotations

import json

import pytest
from price_radar_http import PinnedResponse

from qualify import WOO_PAGE_SIZE, qualify_candidate


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


class Fake16688Client:
    normalize_url = staticmethod(__import__("price_radar_http").PinnedHTTPSClient.normalize_url)

    def __init__(self):
        self.post_calls: list[tuple[str, dict[str, object]]] = []

    def post_json(self, url: str, payload: dict[str, object], *, accept: str = "application/json") -> PinnedResponse:
        url = self.normalize_url(url)
        self.post_calls.append((url, payload))
        if url.endswith("/shopApi/shop/detail"):
            document = {"code": 1, "data": {"shop_no": "S343514", "name": "派大星（900多人群）"}}
        else:
            document = {
                "code": 1,
                "data": {
                    "list": [
                        {
                            "goods_no": "G1",
                            "name": "官方充值 Plus CDK",
                            "description": "商品详情",
                            "content": "GP.T Plus 1个月官方订阅充值",
                            "instruction": "质保30天",
                        },
                        {"goods_no": "G2", "name": "普通商品"},
                    ],
                },
            }
        return PinnedResponse(200, {"content-type": "application/json"}, json.dumps(document, ensure_ascii=False).encode())


def _json_route(payload, *, status=200, content_type="application/json", headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response_headers = {"content-type": content_type}
    if headers:
        response_headers.update({str(key).casefold(): str(value) for key, value in headers.items()})

    def handler(_url, _accept):
        return PinnedResponse(status, response_headers, body)

    return handler


def _woo_page_route(products, *, total=None, totalpages=None):
    total = total if total is not None else len(products)
    totalpages = totalpages if totalpages is not None else max(1, (total + 49) // 50)
    return _json_route(
        products,
        headers={"X-WP-Total": str(total), "X-WP-TotalPages": str(totalpages)},
    )


def _woo_product(item_id, name, slug):
    return {
        "id": item_id,
        "name": name,
        "slug": slug,
        "permalink": f"https://woo-pages.example.com/product/{slug}",
        "is_purchasable": True,
        "is_in_stock": True,
        "prices": {"price": "100", "currency_code": "CNY", "currency_minor_unit": 2},
    }


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
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
    })
    result = qualify_candidate(f"{origin}/products/chatgpt-plus", "unknown", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "woocommerce"
    assert result.detected_source_url == origin
    assert result.ai_product_count == 1
    assert result.sample_products[0]["name"] == "ChatGPT Plus 1 month"
    assert result.sample_products[0]["url"] == f"{origin}/product/chatgpt-plus"
    assert result.confidence_score == 88
    assert result.fingerprints == ["woocommerce-store-api"]


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
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
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
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "validation_failed"


@pytest.mark.parametrize("bad_prices", [
    {"price": "100", "currency_code": "FOO", "currency_minor_unit": 2},
    {"price": "100", "regular_price": "abc", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "100", "sale_price": "abc", "currency_code": "CNY", "currency_minor_unit": 2},
    {"price": "100", "price_range": {"min_amount": "abc", "max_amount": "200"}, "currency_code": "CNY", "currency_minor_unit": 2},
])
def test_woocommerce_connector_price_contract_is_enforced(bad_prices):
    origin = "https://woo-contract.example.com"
    products = [{
        "id": 4,
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
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "validation_failed"


def test_woocommerce_empty_currency_defaults_to_cny_like_connector():
    origin = "https://woo-default-currency.example.com"
    products = [{
        "id": 7,
        "name": "ChatGPT Plus 1 month",
        "slug": "chatgpt-plus",
        "permalink": f"{origin}/product/chatgpt-plus",
        "is_purchasable": True,
        "is_in_stock": True,
        "prices": {"price": "100", "currency_code": "", "currency_minor_unit": 2},
    }]
    client = FakeClient({
        **_probe_routes(origin),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(products),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 1


@pytest.mark.parametrize("handler", [
    lambda products: _json_route(products),
    lambda products: _json_route(products, headers={"X-WP-Total": "2", "X-WP-TotalPages": "1"}),
])
def test_woocommerce_pagination_headers_are_required_and_consistent(handler):
    origin = "https://woo-pagination.example.com"
    products = [{
        "id": 5,
        "name": "ChatGPT Plus 1 month",
        "slug": "chatgpt-plus",
        "permalink": f"{origin}/product/chatgpt-plus",
        "is_purchasable": True,
        "is_in_stock": True,
        "prices": {"price": "100", "currency_code": "CNY", "currency_minor_unit": 2},
    }]
    client = FakeClient({
        **_probe_routes(origin),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(products),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": handler(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "validation_failed"


def test_woocommerce_duplicate_product_ids_are_rejected():
    origin = "https://woo-duplicate.example.com"
    products = [
        {
            "id": 6,
            "name": "ChatGPT Plus 1 month",
            "slug": "chatgpt-plus",
            "permalink": f"{origin}/product/chatgpt-plus",
            "is_purchasable": True,
            "is_in_stock": True,
            "prices": {"price": "100", "currency_code": "CNY", "currency_minor_unit": 2},
        },
        {
            "id": 6,
            "name": "Claude Pro 1 month",
            "slug": "claude-pro",
            "permalink": f"{origin}/product/claude-pro",
            "is_purchasable": True,
            "is_in_stock": True,
            "prices": {"price": "200", "currency_code": "CNY", "currency_minor_unit": 2},
        },
    ]
    client = FakeClient({
        **_probe_routes(origin),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(products),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=50": _woo_page_route(products),
    })
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "validation_failed"


def test_woocommerce_partial_scan_is_not_high_confidence():
    origin = "https://woo-pages.example.com"
    routes = {
        **_probe_routes(origin),
        f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1": _json_route(
            [_woo_product(1, "ChatGPT Plus 1 month", "chatgpt-plus")]
        ),
    }
    pages = [
        [_woo_product(index, "ChatGPT Plus 1 month" if index == 1 else f"Product {index}", f"product-{index}")
         for index in range(page * WOO_PAGE_SIZE + 1, (page + 1) * WOO_PAGE_SIZE + 1)]
        for page in range(3)
    ]
    for page_number, products in enumerate(pages, start=1):
        routes[f"{origin}/wp-json/wc/store/v1/products?page={page_number}&per_page=50"] = _woo_page_route(
            products,
            total=200,
            totalpages=4,
        )
    client = FakeClient(routes)
    result = qualify_candidate(origin, "woocommerce", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 1
    assert result.confidence_score == 49
    assert "woocommerce-partial-scan" in result.fingerprints
    assert "page=4" not in " ".join(client.calls)


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


def test_16688_alias_qualifies_and_uses_canonical_shop_number():
    client = Fake16688Client()
    result = qualify_candidate("https://www.16688.com.cn/shop/HARVEY", "16688", client=client)
    assert result.status == "detected"
    assert result.detected_platform == "16688"
    assert result.detected_source_key == result.detected_source_url == "https://www.16688.com.cn/shop/S343514"
    assert result.total_product_count == 2
    assert result.ai_product_count == 1
    assert result.sample_products[0]["url"] == "https://www.16688.com.cn/goods/G1"
    assert result.fingerprints == ["16688-public-api"]
    assert result.confidence_score == 88
    assert len(client.post_calls) == 3


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


@pytest.mark.parametrize("bad_price", ["contact us", "NaN", "Infinity", "-1", "1e1000000", "1e-1000000"])
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


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16-le", "utf-16-be"])
def test_schema_org_dtd_entity_sitemap_fails_validation(encoding):
    origin = "https://dtd-schema.example.com"
    entry = f"{origin}/sitemap.xml"
    document = """<?xml version="1.0"?>
    <!DOCTYPE urlset [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>&xxe;</loc></url></urlset>"""
    prefix = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}.get(encoding, b"")
    body = prefix + document.encode(encoding)
    client = FakeClient({
        **_probe_routes(origin),
        entry: _xml_route(body),
    })
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "validation_failed"
    assert "DTD" in result.failure_reason


def test_schema_org_invalid_iso_currency_is_not_qualified():
    origin = "https://structured-currency.example.com"
    page = f"{origin}/products/chatgpt"
    body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "ChatGPT Plus 月卡",
        "url": "{page}",
        "offers": {{"@type": "Offer", "price": "100", "priceCurrency": "FOO"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        page: _html_route(body),
    })
    result = qualify_candidate(page, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0


def test_schema_org_sitemap_sampling_truncates_instead_of_rejecting():
    origin = "https://sampling-schema.example.com"
    entry = f"{origin}/sitemap.xml"
    page_urls = [f"{origin}/products/product-{index}" for index in range(100)]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{page}</loc></url>" for page in page_urls)
        + "</urlset>"
    ).encode("utf-8")
    ai_page = page_urls[0]
    ai_body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Claude Pro 月卡",
        "url": "{ai_page}",
        "offers": {{"@type": "Offer", "price": "99", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    routes = {
        **_probe_routes(origin),
        entry: _xml_route(sitemap),
        ai_page: _html_route(ai_body),
    }
    client = FakeClient(routes)
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 1
    assert result.detected_source_url == entry
    sampled_pages = [url for url in client.calls if "/products/product-" in url]
    assert len(set(sampled_pages)) == 1  # 找到 AI 商品后立即停止，其余页面不会被请求
    assert page_urls[8] not in client.calls


def test_schema_org_root_with_large_sitemap_keeps_root_and_qualifies():
    origin = "https://root-sampling.example.com"
    page_urls = [f"{origin}/products/product-{index}" for index in range(100)]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{page}</loc></url>" for page in page_urls)
        + "</urlset>"
    ).encode("utf-8")
    ai_page = page_urls[0]
    ai_body = f"""<html><head>
      <script type="application/ld+json">{{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Gemini Advanced 月卡",
        "url": "{ai_page}",
        "offers": {{"@type": "Offer", "price": "120", "priceCurrency": "CNY"}}
      }}</script>
    </head></html>""".encode("utf-8")
    client = FakeClient({
        **_probe_routes(origin),
        f"{origin}/": _html_route(b"<html><head></head><body>root</body></html>"),
        f"{origin}/sitemap.xml": _xml_route(sitemap),
        ai_page: _html_route(ai_body),
    })
    result = qualify_candidate(origin, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 1
    assert result.detected_source_url.rstrip("/") == origin
    assert result.detected_source_key.rstrip("/") == origin


def test_schema_org_sampling_stops_at_budget_without_rejecting():
    origin = "https://sampling-budget.example.com"
    entry = f"{origin}/sitemap.xml"
    page_urls = [f"{origin}/products/product-{index}" for index in range(100)]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{page}</loc></url>" for page in page_urls)
        + "</urlset>"
    ).encode("utf-8")
    routes = {
        **_probe_routes(origin),
        entry: _xml_route(sitemap),
    }
    # 只提供前 8 个页面：第 9 个页面若被请求会触发 unexpected URL（与真实网络错误等价）。
    for page in page_urls[:8]:
        routes[page] = _html_route(b"<html><body>ordinary page</body></html>")
    client = FakeClient(routes)
    result = qualify_candidate(entry, "schema_org", client=client)
    assert result.status == "detected"
    assert result.ai_product_count == 0
    assert page_urls[8] not in client.calls


def test_private_or_invalid_source_is_validation_failed():
    result = qualify_candidate("https://127.0.0.1/", "unknown", client=FakeClient({}))
    assert result.status == "validation_failed"
    assert result.ai_product_count == 0
