import json
from urllib.parse import urlsplit

import pytest
from price_radar_http import PinnedHTTPSClient as RealPinnedHTTPSClient
from price_radar_http import PinnedResponse

from connectors import schema_org


def _response(body: str | bytes, **headers: str) -> PinnedResponse:
    payload = body.encode("utf-8") if isinstance(body, str) else body
    return PinnedResponse(200, headers, payload)


def _sitemap_index(*locations: str) -> str:
    values = "".join(f"<sitemap><loc>{location}</loc></sitemap>" for location in locations)
    return f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{values}</sitemapindex>'


def _urlset(*locations: str) -> str:
    values = "".join(f"<url><loc>{location}</loc></url>" for location in locations)
    return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{values}</urlset>'


def _html(*documents: object, visible: str = "") -> str:
    scripts = "".join(
        '<script type="application/ld+json">'
        + (document if isinstance(document, str) else json.dumps(document))
        + "</script>"
        for document in documents
    )
    return f"<html><body>{visible}{scripts}</body></html>"


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, responses: dict[str, PinnedResponse]):
    calls: list[tuple[str, str]] = []
    constructor_kwargs: list[dict[str, object]] = []

    class FakeClient:
        normalize_url = staticmethod(RealPinnedHTTPSClient.normalize_url)

        def __init__(self, **kwargs: object) -> None:
            constructor_kwargs.append(kwargs)

        def get(self, url: str, *, accept: str) -> PinnedResponse:
            calls.append((url, accept))
            try:
                return responses[url]
            except KeyError as exc:
                raise AssertionError(f"unexpected request: {url}") from exc

    monkeypatch.setattr(schema_org, "PinnedHTTPSClient", FakeClient)
    return calls, constructor_kwargs


def test_schema_org_connector_reads_sitemap_index_and_jsonld_shapes(monkeypatch):
    root = "https://shop.example/sitemap.xml"
    product_sitemap = "https://shop.example/products-sitemap.xml"
    page_urls = [f"https://shop.example/products/{index}" for index in range(1, 5)]
    responses = {
        root: _response(_sitemap_index(product_sitemap), **{"content-type": "application/xml"}),
        product_sitemap: _response(_urlset(*page_urls), **{"content-type": "application/xml"}),
        page_urls[0]: _response(_html({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Single offer",
            "sku": "ONE",
            "category": "Subscriptions",
            "url": "/products/1",
            "offers": {
                "@type": "Offer",
                "price": "20.00",
                "priceCurrency": "usd",
                "availability": "https://schema.org/InStock",
            },
        }), **{"content-type": "text/html"}),
        page_urls[1]: _response(_html([{
            "@type": ["Thing", "https://schema.org/Product"],
            "name": "Offer list",
            "productID": "LIST-2",
            "category": {"@type": "Thing", "name": "AI"},
            "mainEntityOfPage": {"@id": "/products/2"},
            "offers": [
                {"@type": "Offer", "price": "29.00", "priceCurrency": "USD"},
                {"@type": "Offer", "price": "25.00", "priceCurrency": "USD"},
            ],
        }]), **{"content-type": "text/html"}),
        page_urls[2]: _response(_html({
            "@context": "https://schema.org",
            "@graph": [{
                "@type": "Product",
                "name": "Aggregate offer",
                "sku": "AGG-3",
                "offers": {
                    "@type": "AggregateOffer",
                    "lowPrice": 9.5,
                    "highPrice": 19.5,
                    "priceCurrency": "EUR",
                    "availability": "OutOfStock",
                },
            }],
        }), **{"content-type": "text/html"}),
        page_urls[3]: _response(_html({
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Product",
                    "name": "Referenced offer",
                    "sku": "REF-4",
                    "offers": {"@id": "#offer-4"},
                },
                {
                    "@id": "#offer-4",
                    "@type": "Offer",
                    "priceSpecification": {
                        "@type": "UnitPriceSpecification",
                        "price": "7.25",
                        "priceCurrency": "CNY",
                    },
                    "availability": "https://schema.org/PreOrder",
                },
            ],
        }), **{"content-type": "text/html"}),
    }
    calls, constructor_kwargs = _install_fake_client(monkeypatch, responses)

    records = list(schema_org.load_records("https://shop.example"))

    assert [record["product_name"] for record in records] == [
        "Single offer",
        "Offer list",
        "Aggregate offer",
        "Referenced offer",
    ]
    assert records[0]["product_key"] == "sku:ONE"
    assert records[0]["product_url"] == page_urls[0]
    assert records[0]["listed_price"] == "20.00"
    assert records[0]["currency"] == "USD"
    assert records[0]["product_status"] == "in_stock"
    assert records[0]["category_name"] == "Subscriptions"
    assert records[1]["product_key"] == "productID:LIST-2"
    assert records[1]["listed_price"] == "25.00"
    assert records[1]["category_name"] == "AI"
    assert records[2]["listed_price"] == "9.5"
    assert records[2]["currency"] == "EUR"
    assert records[2]["stock_count"] == 0
    assert records[3]["listed_price"] == "7.25"
    assert records[3]["product_status"] == "pre_order"
    assert all(record["source_platform"] == "schema_org" for record in records)
    assert all(record["source_kind"] == "sitemap_jsonld" for record in records)
    assert len({record["token"] for record in records}) == 1
    assert [url for url, _accept in calls] == [root, product_sitemap, *page_urls]
    assert constructor_kwargs == [{
        "max_response_bytes": schema_org.MAX_RESPONSE_BYTES,
        "max_task_bytes": schema_org.MAX_TOTAL_BYTES,
        "max_task_seconds": schema_org.MAX_TOTAL_SECONDS,
        "request_timeout": schema_org.REQUEST_TIMEOUT_SECONDS,
        "user_agent": "AI-Price-Radar-Importer/3.6",
    }]


def test_schema_org_connector_skips_invalid_incomplete_and_duplicate_jsonld(monkeypatch):
    sitemap = "https://shop.example/catalog.xml"
    page = "https://shop.example/products/valid"
    valid = {
        "@type": "Product",
        "name": "Valid product",
        "sku": "DEDUPED",
        "offers": {"price": "12.00", "priceCurrency": "USD"},
    }
    responses = {
        sitemap: _response(_urlset(page)),
        page: _response(_html(
            "{not valid json",
            {"@type": "Product", "name": "Missing offer"},
            {"@type": "Product", "name": "Missing currency", "offers": {"price": "1.00"}},
            {"@type": "Product", "name": "Negative", "offers": {"price": "-1", "priceCurrency": "USD"}},
            valid,
            valid,
            visible='<div class="price">$0.01</div>',
        )),
    }
    _install_fake_client(monkeypatch, responses)

    records = list(schema_org.load_records(sitemap))

    assert len(records) == 1
    assert records[0]["product_name"] == "Valid product"
    assert records[0]["listed_price"] == "12.00"


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "data:text/html,hello",
        "file:///C:/secrets.txt",
        "http://shop.example/products/unsafe",
        "https://user:password@shop.example/products/unsafe",
        "https://shop.example/products/unsafe#details",
        "https://shop.example:444/products/unsafe",
        "https://other.example/products/unsafe",
    ],
)
def test_schema_org_connector_discards_unsafe_jsonld_product_urls(monkeypatch, unsafe_url):
    sitemap = "https://shop.example/sitemap.xml"
    page = "https://shop.example/products/safe-page"
    responses = {
        sitemap: _response(_urlset(page)),
        page: _response(_html({
            "@type": "Product",
            "name": "Safe fallback",
            "sku": "SAFE",
            "url": unsafe_url,
            "offers": {"price": "1.00", "priceCurrency": "USD"},
        })),
    }
    calls, _constructor_kwargs = _install_fake_client(monkeypatch, responses)

    record = next(iter(schema_org.load_records(sitemap)))

    assert record["product_url"] == page
    assert [url for url, _accept in calls] == [sitemap, page]


@pytest.mark.parametrize(
    "unsafe_entry",
    [
        "http://shop.example/sitemap.xml",
        "https://user:password@shop.example/sitemap.xml",
        "https://shop.example/sitemap.xml#part",
        "https://shop.example:444/sitemap.xml",
        "file:///C:/sitemap.xml",
    ],
)
def test_schema_org_connector_rejects_unsafe_entry_urls(monkeypatch, unsafe_entry):
    _install_fake_client(monkeypatch, {})
    with pytest.raises(ValueError):
        list(schema_org.load_records(unsafe_entry))


def test_schema_org_connector_skips_cross_origin_and_unsafe_sitemap_locations(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    safe_page = "https://shop.example/products/safe"
    responses = {
        sitemap: _response(_urlset(
            safe_page,
            "https://other.example/products/cross-origin",
            "http://shop.example/products/http",
            "https://shop.example:444/products/port",
            "https://user:password@shop.example/products/credentials",
            "https://shop.example/products/fragment#details",
        )),
        safe_page: _response(_html({
            "@type": "Product",
            "name": "Only safe",
            "offers": {"price": 0, "priceCurrency": "CNY"},
        })),
    }
    calls, _constructor_kwargs = _install_fake_client(monkeypatch, responses)

    records = list(schema_org.load_records(sitemap))

    assert len(records) == 1
    assert records[0]["listed_price"] == "0"
    assert [url for url, _accept in calls] == [sitemap, safe_page]


@pytest.mark.parametrize(
    ("limit_name", "limit", "responses", "message"),
    [
        (
            "MAX_SITEMAP_DEPTH",
            1,
            {
                "https://shop.example/sitemap.xml": _response(_sitemap_index("https://shop.example/a.xml")),
                "https://shop.example/a.xml": _response(_sitemap_index("https://shop.example/b.xml")),
            },
            "recursion depth",
        ),
        (
            "MAX_SITEMAPS",
            2,
            {
                "https://shop.example/sitemap.xml": _response(_sitemap_index(
                    "https://shop.example/a.xml",
                    "https://shop.example/b.xml",
                )),
            },
            "sitemap count",
        ),
        (
            "MAX_PRODUCT_URLS",
            1,
            {
                "https://shop.example/sitemap.xml": _response(_urlset(
                    "https://shop.example/products/1",
                    "https://shop.example/products/2",
                )),
            },
            "product URL",
        ),
    ],
)
def test_schema_org_connector_enforces_sitemap_and_url_budgets(
    monkeypatch,
    limit_name,
    limit,
    responses,
    message,
):
    monkeypatch.setattr(schema_org, limit_name, limit)
    _install_fake_client(monkeypatch, responses)

    with pytest.raises(ValueError, match=message):
        list(schema_org.load_records("https://shop.example/sitemap.xml"))


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(b"x" * 33), "size limit"),
        (_response("<urlset />", **{"content-encoding": "gzip"}), "compressed"),
        (PinnedResponse(302, {"location": "https://shop.example/other.xml"}, b""), "HTTP 302"),
    ],
)
def test_schema_org_connector_rejects_oversized_compressed_and_redirected_responses(
    monkeypatch,
    response,
    message,
):
    monkeypatch.setattr(schema_org, "MAX_RESPONSE_BYTES", 32)
    _install_fake_client(monkeypatch, {"https://shop.example/sitemap.xml": response})

    with pytest.raises(ValueError, match=message):
        list(schema_org.load_records("https://shop.example/sitemap.xml"))


def test_schema_org_connector_rejects_entity_expansion(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    malicious = b'<!DOCTYPE x [<!ENTITY boom "expanded">]><urlset><url><loc>&boom;</loc></url></urlset>'
    _install_fake_client(monkeypatch, {sitemap: _response(malicious)})

    with pytest.raises(ValueError, match="DTD or entity"):
        list(schema_org.load_records(sitemap))


def test_schema_org_connector_enforces_total_byte_budget(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    page = "https://shop.example/products/large-total"
    sitemap_body = _urlset(page)
    page_body = _html({
        "@type": "Product",
        "name": "Too large in aggregate",
        "offers": {"price": "1", "priceCurrency": "USD"},
    })
    monkeypatch.setattr(schema_org, "MAX_TOTAL_BYTES", len(sitemap_body.encode()) + len(page_body.encode()) - 1)
    _install_fake_client(monkeypatch, {
        sitemap: _response(sitemap_body),
        page: _response(page_body),
    })

    with pytest.raises(ValueError, match="total byte"):
        list(schema_org.load_records(sitemap))


def test_schema_org_connector_enforces_total_time_budget(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    page = "https://shop.example/products/slow"
    clock = iter([0.0, 0.0, 0.0, schema_org.MAX_TOTAL_SECONDS + 1])
    monkeypatch.setattr(schema_org.time, "monotonic", lambda: next(clock))
    calls, _constructor_kwargs = _install_fake_client(monkeypatch, {
        sitemap: _response(_urlset(page)),
    })

    with pytest.raises(TimeoutError, match="total time"):
        list(schema_org.load_records(sitemap))
    assert [url for url, _accept in calls] == [sitemap]


def test_schema_org_connector_requires_one_unambiguous_currency(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    page = "https://shop.example/products/multi-currency"
    responses = {
        sitemap: _response(_urlset(page)),
        page: _response(_html({
            "@type": "Product",
            "name": "Ambiguous currencies",
            "offers": [
                {"price": "1", "priceCurrency": "USD"},
                {"price": "1", "priceCurrency": "EUR"},
            ],
        })),
    }
    _install_fake_client(monkeypatch, responses)

    assert list(schema_org.load_records(sitemap)) == []


def test_schema_org_connector_never_requests_jsonld_urls(monkeypatch):
    sitemap = "https://shop.example/sitemap.xml"
    page = "https://shop.example/products/listed"
    responses = {
        sitemap: _response(_urlset(page)),
        page: _response(_html({
            "@type": "Product",
            "name": "Canonical only",
            "url": "https://shop.example/products/canonical",
            "offers": {"price": "2.00", "priceCurrency": "USD"},
        })),
    }
    calls, _constructor_kwargs = _install_fake_client(monkeypatch, responses)

    record = next(iter(schema_org.load_records(sitemap)))

    assert record["product_url"] == "https://shop.example/products/canonical"
    assert [urlsplit(url).path for url, _accept in calls] == ["/sitemap.xml", "/products/listed"]
