from __future__ import annotations

import io
from http.client import IncompleteRead
import socket
import threading
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


def test_authenticated_post_uses_original_url_and_pinned_tls_host_without_redirecting():
    sent: list[bytes] = []
    connections = []
    tls = FakeTLSContext()

    class CapturingSocket(FakeSocket):
        def sendall(self, request: bytes):
            sent.append(request)

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda address, **_kwargs: connections.append(address) or CapturingSocket(
            b"HTTP/1.1 302 Found\r\nLocation: https://other.example/steal\r\nContent-Length: 0\r\n\r\n"
        ),
        ssl_context=tls,
    )
    with pytest.raises(ValueError, match="redirects"):
        client.post_json("https://relay.example/prefix/v1/chat/completions", {"model": "test"}, headers={"Authorization": "Bearer test-only"})
    assert connections == [("93.184.216.34", 443)]
    assert tls.server_names == ["relay.example"]
    assert len(sent) == 1
    assert sent[0].startswith(b"POST /prefix/v1/chat/completions HTTP/1.1\r\nHost: relay.example\r\n")
    assert b"Authorization: Bearer test-only\r\n" in sent[0]


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer secret\r\nHost: attacker.example"},
    {"X-Api-Key": "secret\x00"},
    {"Host": "attacker.example"},
    {"X-Api-Key": "非ASCII密钥"},
])
def test_invalid_credential_headers_are_rejected_before_connection(headers):
    def must_not_connect(*_args, **_kwargs):
        pytest.fail("invalid credentials must never reach a connection")

    client = PinnedHTTPSClient(connector=must_not_connect)
    with pytest.raises(ValueError, match="header"):
        client.post_json("https://relay.example/v1/messages", {}, headers=headers)


def test_api_key_is_never_sent_to_private_dns_address():
    connections = []
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
        connector=lambda address, **_kwargs: connections.append(address),
    )
    with pytest.raises(ValueError, match="non-public"):
        client.post_json("https://relay.example/v1/messages", {}, headers={"x-api-key": "secret"})
    assert connections == []


def test_authenticated_model_get_uses_pinned_host_and_refuses_redirects():
    sent = []

    class RecordingSocket(FakeSocket):
        def sendall(self, request):
            sent.append(request)

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: RecordingSocket(response(b"", status=302)),
        ssl_context=FakeTLSContext(),
    )
    with pytest.raises(ValueError, match="redirects"):
        client.get("https://relay.example/prefix/v1/models", accept="application/json", headers={"Authorization": "Bearer test-key"})
    assert len(sent) == 1
    assert sent[0].startswith(b"GET /prefix/v1/models HTTP/1.1\r\n")
    assert b"Authorization: Bearer test-key\r\n" in sent[0]
    assert b"Host: relay.example\r\n" in sent[0]


def test_stream_callback_receives_network_fragment_before_response_finishes():
    client_socket, server_socket = socket.socketpair()
    delivered = threading.Event()
    before_finish = []

    def serve():
        try:
            server_socket.recv(4096)
            server_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\ndata: first\n\n")
            before_finish.append(delivered.wait(2))
            server_socket.sendall(b"data: last\n\n")
        finally:
            server_socket.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: client_socket,
        ssl_context=FakeTLSContext(),
    )
    chunks = []

    def receive(chunk):
        chunks.append(chunk)
        if b"first" in b"".join(chunks):
            delivered.set()

    result = client.post_json("https://relay.example/v1/chat/completions", {}, on_chunk=receive)
    thread.join(3)
    assert before_finish == [True]
    assert result.body == b"data: first\n\ndata: last\n\n" == b"".join(chunks)


def test_connection_timing_includes_tcp_tls_and_excludes_dns(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("price_radar_http.pinned.time.monotonic", lambda: clock[0])

    def resolver(*_args, **_kwargs):
        clock[0] += 5
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    def connector(*_args, **_kwargs):
        clock[0] += .012
        return FakeSocket(response(b"{}"))

    class TimedTLS(FakeTLSContext):
        def wrap_socket(self, raw, server_hostname):
            clock[0] += .018
            return super().wrap_socket(raw, server_hostname)

    client = PinnedHTTPSClient(resolver=resolver, connector=connector, ssl_context=TimedTLS())
    assert client.post_json("https://relay.example", {}).connect_latency_ms == 30


def test_streaming_keeps_byte_budget_and_never_delivers_oversized_chunk():
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: FakeSocket(response(b"123456789")),
        ssl_context=FakeTLSContext(), max_response_bytes=8,
    )
    chunks = []
    with pytest.raises(ValueError, match="size limit"):
        client.post_json("https://relay.example", {}, on_chunk=chunks.append)
    assert chunks == []


def test_stream_read_cannot_bypass_total_deadline(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("price_radar_http.pinned.time.monotonic", lambda: clock[0])

    class SlowBody(io.BytesIO):
        def read1(self, size):
            clock[0] += 2
            return super().read1(size)

    class SlowSocket(FakeSocket):
        def makefile(self, *_args, **_kwargs):
            return SlowBody(self.response)

    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: SlowSocket(response(b"data: text\n\n")),
        ssl_context=FakeTLSContext(), max_task_seconds=1,
    )
    chunks = []
    with pytest.raises(TimeoutError, match="total time limit"):
        client.post_json("https://relay.example", {}, on_chunk=chunks.append)
    assert chunks == []


def test_premature_eof_with_content_length_rejects_even_a_finished_sse_event():
    body = b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n'
    wire = f"HTTP/1.1 200 OK\r\nContent-Length: {len(body) + 10}\r\nConnection: close\r\n\r\n".encode() + body
    client = PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: FakeSocket(wire),
        ssl_context=FakeTLSContext(),
    )
    with pytest.raises(IncompleteRead) as error:
        client.post_json("https://relay.example", {}, on_chunk=lambda _chunk: None)
    assert error.value.expected == 10
