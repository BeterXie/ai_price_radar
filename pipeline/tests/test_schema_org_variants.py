import copy
import json

from price_radar_http import PinnedHTTPSClient, PinnedResponse
from connectors import schema_org


def html(*documents, links=""):
    scripts = "".join('<script type="application/ld+json">' + json.dumps(document) + '</script>' for document in documents)
    return PinnedResponse(200, {"content-type": "text/html"}, ("<html>" + links + scripts + "</html>").encode())


def install(monkeypatch, responses):
    calls = []

    class Client:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **kwargs):
            pass

        def get(self, url, *, accept):
            calls.append(url)
            assert url in responses, f"unexpected request {url}"
            return responses[url]

    monkeypatch.setattr(schema_org, "PinnedHTTPSClient", Client)
    return calls


def sitemap(*urls):
    xml = "<urlset>" + "".join(f"<url><loc>{url}</loc></url>" for url in urls) + "</urlset>"
    return PinnedResponse(200, {"content-type": "application/xml"}, xml.encode())


def test_root_imports_same_origin_product_links_and_reuses_preloaded_page(monkeypatch):
    root = "https://shop.example/"
    detail = root + "product/chatgpt"
    home = ''.join(f'<a href="/{language}">language</a>' for language in ('', 'en', 'ru', 'ja', 'pt', 'es', 'ar', 'zh-hant'))
    home += '<a href="//other.example/product/a">outside</a><a href="https://127.0.0.1/product/a">private</a>'
    home += '<a href="https://user:password@shop.example/product/a">credentials</a><a href="https://shop.example:444/product/a">port</a>'
    home += '<a href="/product/chatgpt">product</a><a href="/product/chatgpt">duplicate</a>'
    calls = install(monkeypatch, {
        root: html({"@type": "WebSite", "name": "Shop"}, links=home),
        detail: html({"@type": "Product", "name": "ChatGPT", "offers": {"name": "Plus", "price": "132", "priceCurrency": "CNY"}}),
    })
    records = list(schema_org.load_records(root))
    assert calls == [root, detail]
    assert len(records) == 1
    assert records[0]["shop_url"] == root.rstrip('/')
    assert records[0]["product_url"] == detail
    assert records[0]["product_name"] == "ChatGPT · Plus"


def test_named_tiers_keep_each_price_currency_stock_and_raw_metadata(monkeypatch):
    page = "https://shop.example/product/chatgpt"
    offers = [
        {"name": "Go", "price": "58", "priceCurrency": "CNY", "availability": "InStock"},
        {"name": "Plus", "price": "132", "priceCurrency": "CNY", "availability": "OutOfStock"},
        {"name": "Pro 5x", "price": "698", "priceCurrency": "CNY", "availability": "PreOrder", "description": "Five times quota"},
        {"name": "Pro 10x", "price": "1280", "priceCurrency": "CNY", "availability": "InStock"},
        {"name": "Pro 25x", "price": "500", "priceCurrency": "USD", "availability": "InStock"},
    ]
    document = {"@type": "Product", "name": "ChatGPT", "sku": "chatgpt", "description": "Subscriptions", "offers": offers + [copy.deepcopy(offers[1])]}
    responses = {page: html(document)}
    install(monkeypatch, responses)
    records = list(schema_org.load_records(page))
    assert len(records) == 5
    assert [(record['product_name'], record['listed_price'], record['currency'], record['product_status']) for record in records] == [
        ('ChatGPT · Go', '58', 'CNY', 'in_stock'),
        ('ChatGPT · Plus', '132', 'CNY', 'out_of_stock'),
        ('ChatGPT · Pro 5x', '698', 'CNY', 'pre_order'),
        ('ChatGPT · Pro 10x', '1280', 'CNY', 'in_stock'),
        ('ChatGPT · Pro 25x', '500', 'USD', 'in_stock'),
    ]
    assert records[1]['stock_count'] == 0
    assert records[2]['raw_json']['description'] == 'Subscriptions'
    assert records[2]['raw_json']['schema_org_offer']['description'] == 'Five times quota'
    assert records[2]['raw_json']['offers'] == document['offers']
    original_keys = {record['product_name']: (record['product_key'], record['variant_key']) for record in records}
    changed = copy.deepcopy(document)
    changed['offers'].reverse()
    for offer in changed['offers']:
        offer['price'] = '999'
        offer['availability'] = 'InStock'
    responses[page] = html(changed)
    rerun = list(schema_org.load_records(page))
    assert {record['product_name']: (record['product_key'], record['variant_key']) for record in rerun} == original_keys


def test_language_mirrors_dedupe_identity_without_merging_independent_skus(monkeypatch):
    root = "https://shop.example/sitemap.xml"
    page = "https://shop.example/product/one"
    mirror = "https://shop.example/en/product/one"
    other = "https://shop.example/product/two"
    offers = [
        {"sku": "MONTHLY-A", "name": "Plus", "price": "20", "priceCurrency": "USD"},
        {"sku": "MONTHLY-B", "name": "Plus", "price": "20", "priceCurrency": "USD"},
    ]
    one = {"@type": "Product", "sku": "PRODUCT-ONE", "name": "ChatGPT", "offers": offers}
    translated = copy.deepcopy(one)
    translated['name'] = 'Localized title'
    for offer in translated['offers']:
        offer['name'] = 'Localized plan'
    two = {**one, "sku": "PRODUCT-TWO"}
    install(monkeypatch, {root: sitemap(page, mirror, other), page: html(one), mirror: html(translated), other: html(two)})
    records = list(schema_org.load_records(root))
    assert len(records) == 4
    assert len({record['product_key'] for record in records}) == 4
    assert {record['variant_key'] for record in records} == {'MONTHLY-A', 'MONTHLY-B'}


def test_unnamed_single_offer_keeps_existing_identity_and_name(monkeypatch):
    page = "https://shop.example/product/single"
    install(monkeypatch, {page: html({"@type": "Product", "sku": "SINGLE", "name": "Original", "offers": {"price": "10", "priceCurrency": "USD"}})})
    record, = schema_org.load_records(page)
    assert record['product_name'] == 'Original'
    assert record['product_key'] == 'sku:SINGLE'
    assert record['variant_key'] == 'SINGLE'


def test_invalid_named_offers_do_not_inherit_another_variants_price(monkeypatch):
    page = "https://shop.example/product/mixed"
    offers = [
        {"name": "Missing price", "priceCurrency": "USD"},
        {"name": "Missing currency", "price": "1"},
        {"name": "Negative", "price": "-5", "priceCurrency": "USD"},
        {"name": "Non-finite", "price": "NaN", "priceCurrency": "USD"},
        {"name": "Valid", "price": "12", "priceCurrency": "USD"},
        {"price": "7", "priceCurrency": "CNY"},
    ]
    install(monkeypatch, {page: html({"@type": "Product", "name": "Service", "offers": offers})})
    records = list(schema_org.load_records(page))
    assert [(r['product_name'], r['listed_price'], r['currency']) for r in records] == [
        ('Service · Valid', '12', 'USD'), ('Service', '7', 'CNY'),
    ]
    assert all(r['raw_json']['offers'] == offers for r in records)


def test_linked_non_product_pages_fall_back_to_sitemap_without_refetching(monkeypatch):
    root = "https://shop.example/"
    non_product = root + "product/about"
    detail = root + "product/valid"
    calls = install(monkeypatch, {
        root: html(links='<a href="/product/about">about</a>'),
        non_product: html({"@type": "WebPage"}),
        root + 'sitemap.xml': sitemap(non_product, detail),
        detail: html({"@type": "Product", "name": "Valid", "offers": {"price": "1", "priceCurrency": "USD"}}),
    })
    records = list(schema_org.load_records(root))
    assert len(records) == 1
    assert calls == [root, non_product, root + 'sitemap.xml', detail]
