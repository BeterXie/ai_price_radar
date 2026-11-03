import json
from datetime import datetime, timedelta, timezone

import pytest

from probe import PinnedHTTPSClient, ProbeResponse, probe_source
from storefront_catalog import StaleStorefrontCatalog


def catalog():
    now = datetime.now(timezone.utc)
    return {
        "quoteState": "fresh", "updatedAt": now.isoformat(),
        "validUntil": (now + timedelta(minutes=5)).isoformat(),
        "suppliers": [{"id": "primary", "status": 200, "quoteState": "fresh", "updatedAt": now.isoformat(), "validUntil": (now + timedelta(minutes=5)).isoformat()}],
        "products": [{"id": "plus", "name": "ChatGPT Plus", "supplierId": "primary", "saleEnabled": True, "checkoutSupported": True, "rmbPrice": 72.25, "stock": 3}],
    }


class Client:
    normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

    def __init__(self, document):
        self.document = document
        self.calls = []

    def get(self, url, *, accept):
        self.calls.append(url)
        if url == "https://store.example/":
            return ProbeResponse(200, {"content-type": "text/html"}, '<title>AI 优选 — 数字商城</title><time id="catalog-sync-time"></time><div id="product-grid"></div>'.encode())
        assert url == "https://store.example/api/products"
        return ProbeResponse(200, {"content-type": "application/json"}, json.dumps(self.document).encode())


def test_detect_storefront_home_as_merchant_catalog():
    client = Client(catalog())
    result = probe_source("https://store.example/", client=client)
    assert result.detected_platform == "merchant_json"
    assert result.source_url == result.source_key == "https://store.example/api/products"
    assert result.shop_name == "AI 优选" and result.product_count == 1
    assert client.calls == ["https://store.example/", "https://store.example/api/products"]


def test_detect_storefront_catalog_directly():
    result = probe_source("https://store.example/api/products", client=Client(catalog()))
    assert result.detected_platform == "merchant_json" and result.product_count == 1


@pytest.mark.parametrize("entry", ["https://store.example/", "https://store.example/api/products"])
def test_storefront_fingerprint_does_not_accept_stale_prices(entry):
    document = catalog()
    document["quoteState"] = "stale"
    with pytest.raises(StaleStorefrontCatalog):
        probe_source(entry, client=Client(document))


def test_storefront_qualification_uses_normalized_public_products():
    from qualify import qualify_candidate

    result = qualify_candidate("https://store.example/", "independent", client=Client(catalog()))
    assert result.status == "detected"
    assert result.detected_platform == "merchant_json"
    assert result.total_product_count == result.ai_product_count == 1
    assert result.sample_products[0]["url"] == "https://store.example/product?id=plus"
