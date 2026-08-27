from __future__ import annotations

import io
import socket
import time

import pytest

from price_radar_http import PinnedHTTPSClient


class FakeSocket:
    def __init__(self, response: bytes):
        self.response = response

    def settimeout(self, _timeout):
        pass

    def sendall(self, _request):
        pass

    def makefile(self, *_args, **_kwargs):
        return io.BytesIO(self.response)

    def close(self):
        pass


class FakeTLSContext:
    def __init__(self):
        self.server_names: list[str] = []

    def wrap_socket(self, raw, server_hostname):
        self.server_names.append(server_hostname)
        return raw


def response(body: bytes, *, status: int = 200) -> bytes:
    return f"HTTP/1.1 {status} Test\r\nConnection: close\r\n\r\n".encode() + body


def test_source_sync_resolves_once_and_reuses_the_validated_numeric_ip():
    resolutions = 0
    connections: list[tuple[str, int]] = []
    tls = FakeTLSContext()

    def resolver(*_args, **_kwargs):
        nonlocal resolutions
        resolutions += 1
        address = "93.184.216.34" if resolutions == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    client = PinnedHTTPSClient(
        resolver=resolver,
        connector=lambda address, timeout: connections.append(address) or FakeSocket(response(b"{}")),
        ssl_context=tls,
    )

    client.get("https://shop.example/config", accept="application/json")
    client.get("https://shop.example/products", accept="application/json")

    assert resolutions == 1
    assert connections == [("93.184.216.34", 443), ("93.184.216.34", 443)]
    assert tls.server_names == ["shop.example", "shop.example"]


def test_connect_retries_a_valid_ipv4_address_after_unreachable_ipv6_and_pins_it():
    resolutions = 0
    connections: list[tuple[str, int]] = []
    ipv6 = "2606:4700:4700::1111"
    ipv4 = "93.184.216.34"

    def resolver(*_args, **_kwargs):
        nonlocal resolutions
        resolutions += 1
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ipv6, 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ipv4, 443)),
        ]

    def connector(address, timeout):
        del timeout
        connections.append(address)
        if address[0] == ipv6:
            raise OSError(101, "Network is unreachable")
        return FakeSocket(response(b"{}"))

    client = PinnedHTTPSClient(resolver=resolver, connector=connector, ssl_context=FakeTLSContext())

    client.get("https://shop.example/config", accept="application/json")
    client.get("https://shop.example/products", accept="application/json")

    assert resolutions == 1
    assert connections == [(ipv6, 443), (ipv4, 443), (ipv4, 443)]


def test_any_non_public_address_rejects_the_entire_resolution_set():
    connected = False

    def connector(*_args, **_kwargs):
        nonlocal connected
        connected = True
        raise AssertionError("connection must not be attempted")

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443)),
        ],
        connector=connector,
    )

    with pytest.raises(ValueError, match="non-public"):
        client.get("https://mixed.example", accept="text/plain")
    assert connected is False


def test_failed_oversized_response_still_consumes_the_total_byte_budget():
    bodies = iter((response(b"x" * 9), response(b"y" * 2)))
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ],
        connector=lambda *_args, **_kwargs: FakeSocket(next(bodies)),
        ssl_context=FakeTLSContext(),
        max_response_bytes=8,
        max_task_bytes=10,
    )

    with pytest.raises(ValueError, match="response exceeds size"):
        client.get("https://large.example/first", accept="text/plain")
    assert client.remaining_bytes == 1
    with pytest.raises(ValueError, match="total size"):
        client.get("https://large.example/second", accept="text/plain")
    assert client.remaining_bytes == -1


def test_dns_resolution_has_a_per_request_timeout_inside_the_source_deadline():
    def slow_resolver(*_args, **_kwargs):
        time.sleep(1)
        return []

    client = PinnedHTTPSClient(
        resolver=slow_resolver,
        request_timeout=0.01,
        max_task_seconds=1,
    )
    started_at = time.monotonic()
    with pytest.raises(TimeoutError, match="DNS resolution"):
        client.get("https://slow.example", accept="text/plain")
    assert time.monotonic() - started_at < 0.5


def test_json_post_writes_utf8_body_and_matching_content_length():
    sent: list[bytes] = []

    class CapturingSocket(FakeSocket):
        def sendall(self, request: bytes):
            sent.append(request)

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ],
        connector=lambda *_args, **_kwargs: CapturingSocket(response(b"{}")),
        ssl_context=FakeTLSContext(),
    )

    client.post_json("https://16688.com.cn/shopApi/shop/detail", {"shop_no": "派大星"})

    body = '{"shop_no":"派大星"}'.encode("utf-8")
    assert len(sent) == 1
    assert sent[0].startswith(b"POST /shopApi/shop/detail HTTP/1.1\r\n")
    assert b"Content-Type: application/json\r\n" in sent[0]
    assert f"Content-Length: {len(body)}\r\n".encode() in sent[0]
    assert sent[0].endswith(b"\r\n\r\n" + body)
