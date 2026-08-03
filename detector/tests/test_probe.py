import io
import json
import socket

import pytest

from probe import PinnedHTTPSClient, ProbeResponse, probe_source


class StubClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    def normalize_url(self, value):
        return PinnedHTTPSClient.normalize_url(value)

    def get(self, value, *, accept):
        return next(self.responses)


def response(document, *, status=200, content_type="application/json"):
    return ProbeResponse(status, {"content-type": content_type}, json.dumps(document).encode())


def test_detector_recognizes_dujiao_brand_overlay():
    client = StubClient([
        response({"status_code": 0, "data": {"brand": {"site_name": "Overlay Store"}}}),
        response({"status_code": 0, "data": [{}], "pagination": {"total": 7}}),
    ])
    result = probe_source("https://shop.example/products/item", client=client)
    assert result.detected_platform == "dujiao_next"
    assert result.source_url == "https://shop.example"
    assert result.shop_name == "Overlay Store"
    assert result.product_count == 7


def test_detector_recognizes_merchant_feed_after_dujiao_probe_fails():
    client = StubClient([
        ProbeResponse(404, {}, b""),
        response({"items": [{"name": "ChatGPT Plus"}], "shop": {"name": "Feed Store"}}),
    ])
    result = probe_source("https://feed.example/catalog.json", client=client)
    assert result.detected_platform == "merchant_json"
    assert result.shop_name == "Feed Store"


def test_detector_rejects_private_addresses_and_non_443_ports():
    client = PinnedHTTPSClient(resolver=lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ValueError, match="non-public"):
        client._public_addresses("example.test")
    with pytest.raises(ValueError, match="port 443"):
        client.normalize_url("https://example.test:8443")


def test_validated_ip_is_used_for_the_actual_connection():
    connected = []
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ],
        connector=lambda address, timeout: connected.append(address) or (_ for _ in ()).throw(OSError("stop")),
    )
    with pytest.raises(OSError, match="stop"):
        client.get("https://example.com", accept="text/html")
    assert connected == [("93.184.216.34", 443)]


def test_detector_refuses_redirects_and_oversized_bodies(monkeypatch):
    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def sendall(self, _request):
            pass

        def makefile(self, *_args, **_kwargs):
            return io.BytesIO(b"HTTP/1.1 302 Found\r\nLocation: https://other.example\r\nContent-Length: 0\r\n\r\n")

        def close(self):
            pass

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            return raw

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: FakeSocket(),
        ssl_context=FakeContext(),
    )
    with pytest.raises(ValueError, match="redirects"):
        client.get("https://example.com", accept="text/html")
