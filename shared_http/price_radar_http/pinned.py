from __future__ import annotations

import http.client
import ipaddress
import queue
import socket
import ssl
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_TOTAL_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class PinnedResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def status_code(self) -> int:
        return self.status


class PinnedHTTPSClient:
    """Bounded HTTPS client that connects only to a previously validated numeric IP."""

    def __init__(
        self,
        *,
        resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
        connector: Callable[..., socket.socket] = socket.create_connection,
        ssl_context: ssl.SSLContext | None = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_task_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
        max_task_seconds: float = DEFAULT_MAX_TOTAL_SECONDS,
        request_timeout: float = 5.0,
        user_agent: str = "AI-Price-Radar-SafeHTTP/1",
    ):
        if min(max_response_bytes, max_task_bytes) <= 0 or min(max_task_seconds, request_timeout) <= 0:
            raise ValueError("HTTPS limits must be positive")
        self.resolver = resolver
        self.connector = connector
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.max_response_bytes = max_response_bytes
        self.remaining_bytes = max_task_bytes
        self.deadline = time.monotonic() + max_task_seconds
        self.request_timeout = request_timeout
        self.user_agent = user_agent
        self._pinned_addresses: dict[tuple[str, int], str] = {}

    @staticmethod
    def normalize_url(value: object) -> str:
        raw = str(value)
        if "\r" in raw or "\n" in raw:
            raise ValueError("source URL contains invalid control characters")
        parsed = urllib.parse.urlsplit(raw)
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() != "https" or not host or parsed.username or parsed.password:
            raise ValueError("source must be a public HTTPS URL")
        if host == "localhost" or host.endswith((".local", ".internal")):
            raise ValueError("source URL contains an internal hostname")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("source port is invalid") from exc
        if port not in (None, 443):
            raise ValueError("source client only permits HTTPS port 443")
        try:
            literal_address = ipaddress.ip_address(host)
        except ValueError:
            host = host.encode("idna").decode("ascii")
        else:
            if not PinnedHTTPSClient._is_public(literal_address):
                raise ValueError("source URL contains a non-public address")
        rendered_host = f"[{host}]" if ":" in host else host
        path = urllib.parse.quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = urllib.parse.quote(parsed.query, safe="=&;%:@!$'()*+,-._~/?")
        return urllib.parse.urlunsplit(("https", rendered_host, path, query, ""))

    def _remaining_seconds(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("source request exceeded total time limit")
        return remaining

    @staticmethod
    def _is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return (
            address.is_global
            and not address.is_private
            and not address.is_loopback
            and not address.is_link_local
            and not address.is_reserved
            and not address.is_unspecified
            and not address.is_multicast
        )

    def _resolve(self, host: str, port: int) -> list[tuple[Any, ...]]:
        results: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

        def resolve() -> None:
            try:
                results.put((True, self.resolver(host, port, type=socket.SOCK_STREAM)))
            except BaseException as exc:
                results.put((False, exc))

        thread = threading.Thread(target=resolve, name="safe-https-resolver", daemon=True)
        thread.start()
        thread.join(min(self.request_timeout, self._remaining_seconds()))
        if thread.is_alive():
            raise TimeoutError("source DNS resolution exceeded total time limit")
        succeeded, value = results.get_nowait()
        if not succeeded:
            if isinstance(value, BaseException):
                raise value
            raise OSError("source DNS resolution failed")
        return list(value)  # type: ignore[arg-type]

    def _public_addresses(self, host: str, port: int = 443) -> list[str]:
        infos = self._resolve(host, port)
        addresses = sorted({str(info[4][0]) for info in infos})
        if not addresses:
            raise ValueError("source hostname did not resolve")
        parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
        if any(not self._is_public(address) for address in parsed_addresses):
            raise ValueError("source hostname resolved to a non-public address")
        return addresses

    def _pinned_address(self, host: str, port: int) -> str:
        key = (host, port)
        cached = self._pinned_addresses.get(key)
        if cached is not None:
            return cached
        addresses = self._public_addresses(host, port)
        selected = addresses[0]
        self._pinned_addresses[key] = selected
        return selected

    def get(self, value: object, *, accept: str) -> PinnedResponse:
        url = self.normalize_url(value)
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or 443
        address = self._pinned_address(host, port)
        timeout = min(self.request_timeout, self._remaining_seconds())
        raw_socket = self.connector((address, port), timeout=timeout)
        tls_socket: ssl.SSLSocket | None = None
        response: http.client.HTTPResponse | None = None
        try:
            raw_socket.settimeout(min(self.request_timeout, self._remaining_seconds()))
            tls_socket = self.ssl_context.wrap_socket(raw_socket, server_hostname=host)
            target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            host_header = f"[{host}]" if ":" in host else host
            request = (
                f"GET {target} HTTP/1.1\r\n"
                f"Host: {host_header}\r\n"
                f"Accept: {accept}\r\n"
                f"User-Agent: {self.user_agent}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            tls_socket.sendall(request)
            response = http.client.HTTPResponse(tls_socket)
            response.begin()
            headers = {key.casefold(): header_value for key, header_value in response.getheaders()}
            if 300 <= response.status < 400:
                raise ValueError("source redirects are not followed")
            try:
                content_length = int(headers.get("content-length") or 0)
            except (TypeError, ValueError):
                content_length = 0
            limit = min(self.max_response_bytes, self.remaining_bytes)
            if content_length > limit:
                raise ValueError("source response exceeds size limit")
            chunks: list[bytes] = []
            response_total = 0
            while True:
                tls_socket.settimeout(min(self.request_timeout, self._remaining_seconds()))
                read_size = min(64 * 1024, self.max_response_bytes - response_total + 1, self.remaining_bytes + 1)
                if read_size <= 0:
                    raise ValueError("source response exceeds total size limit")
                chunk = response.read(read_size)
                if not chunk:
                    break
                response_total += len(chunk)
                self.remaining_bytes -= len(chunk)
                if response_total > self.max_response_bytes:
                    raise ValueError("source response exceeds size limit")
                if self.remaining_bytes < 0:
                    raise ValueError("source response exceeds total size limit")
                chunks.append(chunk)
            return PinnedResponse(response.status, headers, b"".join(chunks))
        finally:
            if response is not None:
                response.close()
            if tls_socket is not None:
                tls_socket.close()
            else:
                raw_socket.close()
