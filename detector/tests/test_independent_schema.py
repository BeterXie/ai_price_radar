import json

import pytest

import probe
from price_radar_http import PinnedHTTPSClient, PinnedResponse
from sitemap import product_links, product_page_urls


class MappingClient:
    normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, *, accept):
        self.calls.append(url)
        assert url in self.responses, f"unexpected request: {url}"
        return self.responses[url]


def html(body):
    return PinnedResponse(200, {"content-type": "text/html"}, body.encode())


def product(name="ChatGPT"):
    return '<script type="application/ld+json">' + json.dumps({
        "@type": "Product", "name": name,
        "offers": [{"name": "Go", "price": "58", "priceCurrency": "CNY"},
                   {"name": "Plus", "price": "132", "priceCurrency": "CNY"}],
    }) + '</script>'


def test_root_finds_linked_product_before_unrelated_api_probes():
    root = "https://shop.example/"
    detail = root + "product/chatgpt"
    languages = ["", "zh-hant", "en", "ru", "ja", "es", "pt", "ar"]
    home = "".join(f'<a href="/{locale}">Language</a>' for locale in languages)
    home += '<a href="https://other.example/product/unsafe">External</a>'
    home += '<a href="https://127.0.0.1/product/unsafe">Private</a>'
    home += '<a href="/product/chatgpt">ChatGPT</a><a href="/product/chatgpt">Again</a>'
    client = MappingClient({root: html(home), detail: html(product())})

    result = probe.probe_source(root, client=client)

    assert result.detected_platform == "schema_org"
    assert result.source_url == result.source_key == root.rstrip("/")
    assert result.product_count == 1
    assert client.calls == [root, detail]


def test_product_entry_keeps_detail_identity_and_is_read_once():
    detail = "https://shop.example/product/chatgpt"
    client = MappingClient({detail: html(product())})
    result = probe.probe_source(detail, client=client)
    assert result.source_key == result.source_url == detail
    assert client.calls == [detail]


def test_sitemap_prefers_product_after_first_eight_language_homes():
    root = "https://shop.example"
    urls = [root + "/" + lang for lang in ("", "zh-hant", "en", "ru", "ja", "es", "pt", "ar")]
    urls += [root + "/product/chatgpt", "https://other.example/product/foreign", "https://[invalid"]
    xml = "<urlset>" + "".join(f"<url><loc>{url}</loc></url>" for url in urls) + "</urlset>"
    client = MappingClient({root + "/sitemap.xml": PinnedResponse(200, {}, xml.encode())})
    result = product_page_urls(root + "/sitemap.xml", root, client)
    assert result[0] == root + "/product/chatgpt"
    assert len(result) == 8
    assert all(url.startswith(root) for url in result)


@pytest.mark.parametrize("unsafe", [
    "https://127.0.0.1/product/a", "https://10.0.0.1/product/a", "//other.example/product/a",
    "http://shop.example/product/a", "https://user:password@shop.example/product/a",
    "https://shop.example:444/product/a", "javascript:alert(1)", "#product/a", "https://[invalid",
])
def test_product_links_reject_unsafe_or_cross_origin_urls(unsafe):
    body = f'<a href="{unsafe}">bad</a><a href="/product/safe">good</a>'.encode()
    client = MappingClient({})
    assert product_links(body, "https://shop.example/", "https://shop.example", client) == [
        "https://shop.example/product/safe",
    ]
    assert client.calls == []


def test_root_uses_one_client_with_existing_task_limits(monkeypatch):
    root = "https://shop.example/"
    detail = root + "product/chatgpt"
    clients = []

    class Client(MappingClient):
        def __init__(self, **limits):
            super().__init__({root: html('<a href="/product/chatgpt">product</a>'), detail: html(product())})
            self.limits = limits
            clients.append(self)

    monkeypatch.setattr(probe, "PinnedHTTPSClient", Client)
    assert probe.probe_source(root).detected_platform == "schema_org"
    assert len(clients) == 1
    assert clients[0].limits["max_task_seconds"] == 15.0
    assert clients[0].limits["max_response_bytes"] == 1024 * 1024
    assert clients[0].limits["max_task_bytes"] == 2 * 1024 * 1024
    assert clients[0].calls == [root, detail]
