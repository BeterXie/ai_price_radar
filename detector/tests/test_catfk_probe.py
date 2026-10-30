import hashlib
import json

import pytest

from probe import PinnedHTTPSClient, ProbeResponse, probe_source


class Client:
    normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post_json(self, url, payload, *, accept="application/json"):
        self.calls.append((url, payload))
        return ProbeResponse(200, {"content-type": "application/json"}, json.dumps(next(self.responses)).encode())

    def get(self, url, *, accept):
        raise AssertionError(f"unexpected generic request {url}")


def valid_client(name_field="nickname"):
    return Client([
        {"code": 1, "data": {name_field: "Independent shop"}},
        {"code": 1, "data": {"total": 14, "list": [{"goods_key": "public-goods", "name": "ChatGPT Plus", "price": "20"}]}},
    ])


@pytest.mark.parametrize("name_field", ["nickname", "name"])
def test_catfk_keeps_origin_and_namespaces_public_shop_identity(name_field):
    client = valid_client(name_field)
    result = probe_source("https://catfk.com/shop/ABC123", client=client)
    assert result.detected_platform == "ldxp"
    assert result.source_url == "https://catfk.com/shop/ABC123"
    assert result.source_key == "catfk:abc123"
    assert result.shop_name == "Independent shop"
    assert result.product_count == 14
    assert [url for url, _ in client.calls] == [
        "https://catfk.com/shopApi/Shop/info", "https://catfk.com/shopApi/Shop/goodsList",
    ]
    assert all(payload['token'] == 'ABC123' for _, payload in client.calls)


def test_catfk_long_public_token_uses_stable_casefold_hash():
    token = "Ab" * 62
    result = probe_source(f"https://catfk.com/shop/{token}", client=valid_client())
    assert result.source_url.endswith(token)
    assert result.source_key == "catfk:sha256:" + hashlib.sha256(token.casefold().encode()).hexdigest()
    assert len(result.source_key) <= 128


def test_catfk_refuses_missing_shop_without_trying_official_hosts():
    client = Client([{"code": 0, "data": None}])
    with pytest.raises(ValueError, match="not a valid catfk"):
        probe_source("https://catfk.com/shop/MISSING", client=client)
    assert len(client.calls) == 1


@pytest.mark.parametrize("data", [{"list": {}}, {"list": ["bad"]}, {"list": [], "total": -1}])
def test_catfk_requires_valid_catalog_shape(data):
    client = Client([{"code": 1, "data": {}}, {"code": 1, "data": data}])
    with pytest.raises(ValueError, match="catfk goods API"):
        probe_source("https://catfk.com/shop/ABC123", client=client)


def test_official_ldxp_identity_does_not_share_catfk_namespace():
    result = probe_source("https://wzyp.cn/shop/ABC123", client=Client([]))
    assert result.source_key == "abc123"
    assert result.source_url == "https://wzyp.cn/shop/ABC123"
