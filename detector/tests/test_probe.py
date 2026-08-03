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
        ProbeResponse(404, {}, b""),
        response({"items": [{"name": "ChatGPT Plus"}], "shop": {"name": "Feed Store"}}),
    ])
    result = probe_source("https://feed.example/catalog.json", client=client)
    assert result.detected_platform == "merchant_json"
    assert result.shop_name == "Feed Store"


def test_detector_recognizes_woocommerce_store_api_before_generic_json():
    client = StubClient([
        ProbeResponse(404, {}, b""),
        ProbeResponse(
            200,
            {"content-type": "application/json", "x-wp-total": "12"},
            json.dumps([{"id": 42, "name": "ChatGPT Plus", "prices": {"currency_code": "USD"}}]).encode(),
        ),
    ])
    result = probe_source("https://woo.example/products/chatgpt", client=client)
    assert result.detected_platform == "woocommerce"
    assert result.source_url == result.source_key == "https://woo.example"
    assert result.product_count == 12


def test_detector_recognizes_schema_org_product_page():
    document = b"""<html><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"ChatGPT Plus"}
    </script></html>"""
    client = StubClient([
        ProbeResponse(404, {}, b""),
        ProbeResponse(404, {}, b""),
        ProbeResponse(404, {}, b""),
        ProbeResponse(200, {"content-type": "text/html"}, document),
    ])
    result = probe_source("https://structured.example/products/chatgpt", client=client)
    assert result.detected_platform == "schema_org"
    assert result.source_url == "https://structured.example/products/chatgpt"
    assert result.product_count == 1


def test_detector_finds_schema_org_product_through_same_origin_sitemap():
    sitemap = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://structured.example/products/chatgpt</loc></url>
    <url><loc>https://other.example/products/ignored</loc></url>
    </urlset>"""
    product = b"""<script type="application/ld+json">
    {"@graph":[{"@type":"Product","name":"ChatGPT Plus"}]}
    </script>"""
    client = StubClient([
        ProbeResponse(404, {}, b""),
        ProbeResponse(404, {}, b""),
        ProbeResponse(404, {}, b""),
        ProbeResponse(200, {"content-type": "text/html"}, b"<html></html>"),
        ProbeResponse(200, {"content-type": "application/xml"}, sitemap),
        ProbeResponse(200, {"content-type": "text/html"}, product),
    ])
    result = probe_source("https://structured.example", client=client)
    assert result.detected_platform == "schema_org"
    assert result.source_url == result.source_key == "https://structured.example"


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.1.1",
        "192.0.2.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fd00::1",
        "2001:db8::1",
        "ff02::1",
    ],
)
def test_detector_rejects_non_public_ipv4_and_ipv6_addresses(address):
    client = PinnedHTTPSClient(resolver=lambda *_args, **_kwargs: [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
    ])
    with pytest.raises(ValueError, match="non-public"):
        client._public_addresses("example.test")


def test_detector_rejects_non_443_ports():
    client = PinnedHTTPSClient()
    with pytest.raises(ValueError, match="port 443"):
        client.normalize_url("https://example.test:8443")


def test_validated_ip_is_used_for_the_actual_connection():
    connected = []
    server_names = []

    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def sendall(self, _request):
            pass

        def makefile(self, *_args, **_kwargs):
            return io.BytesIO(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n")

        def close(self):
            pass

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            server_names.append(server_hostname)
            return raw

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ],
        connector=lambda address, timeout: connected.append(address) or FakeSocket(),
        ssl_context=FakeContext(),
    )
    response = client.get("https://example.com", accept="text/html")
    assert response.status == 204
    assert connected == [("93.184.216.34", 443)]
    assert server_names == ["example.com"]


def test_detector_refuses_redirects():
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


def test_detector_stops_reading_as_soon_as_streamed_body_exceeds_limit():
    body_stream = None

    class TrackingBody(io.BytesIO):
        def __init__(self, value):
            super().__init__(value)
            self.body_bytes_read = 0

        def read(self, size=-1):
            chunk = super().read(size)
            self.body_bytes_read += len(chunk)
            return chunk

    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def sendall(self, _request):
            pass

        def makefile(self, *_args, **_kwargs):
            nonlocal body_stream
            body_stream = TrackingBody(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" + b"x" * 1024)
            return body_stream

        def close(self):
            pass

    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            return raw

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ],
        connector=lambda *_args, **_kwargs: FakeSocket(),
        ssl_context=FakeContext(),
        max_task_bytes=8,
    )
    with pytest.raises(ValueError, match="size limit"):
        client.get("https://example.com", accept="text/plain")
    assert body_stream is not None
    assert body_stream.body_bytes_read == 9
