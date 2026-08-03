from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TASK_BYTES = 2 * 1024 * 1024
MAX_TASK_SECONDS = 15.0
LDXP_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"}
LDXP_PATH = re.compile(r"/shop/([A-Za-z0-9._~-]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ProbeResponse:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class ProbeResult:
    detected_platform: str
    source_url: str
    source_key: str
    shop_name: str = ""
    product_count: int = 0


class PinnedHTTPSClient:
    def __init__(
        self,
        *,
        resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
        connector: Callable[..., socket.socket] = socket.create_connection,
        ssl_context: ssl.SSLContext | None = None,
        max_task_bytes: int = MAX_TASK_BYTES,
        max_task_seconds: float = MAX_TASK_SECONDS,
    ):
        self.resolver = resolver
        self.connector = connector
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.remaining_bytes = max_task_bytes
        self.deadline = time.monotonic() + max_task_seconds

    @staticmethod
    def normalize_url(value: object) -> str:
        parsed = urllib.parse.urlsplit(str(value))
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() != "https" or not host or parsed.username or parsed.password:
            raise ValueError("source must be a public HTTPS URL")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("source port is invalid") from exc
        if port not in (None, 443):
            raise ValueError("source detector only permits HTTPS port 443")
        host = host.encode("idna").decode("ascii")
        rendered_host = f"[{host}]" if ":" in host else host
        return urllib.parse.urlunsplit(("https", rendered_host, parsed.path or "/", parsed.query, ""))

    def _remaining_seconds(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("source detection exceeded total time limit")
        return remaining

    def _public_addresses(self, host: str) -> list[str]:
        infos = self.resolver(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({str(info[4][0]) for info in infos})
        if not addresses:
            raise ValueError("source hostname did not resolve")
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("source hostname resolved to a non-public address")
        return addresses

    def get(self, value: object, *, accept: str) -> ProbeResponse:
        url = self.normalize_url(value)
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        address = self._public_addresses(host)[0]
        timeout = min(5.0, self._remaining_seconds())
        raw_socket = self.connector((address, 443), timeout=timeout)
        tls_socket: ssl.SSLSocket | None = None
        response: http.client.HTTPResponse | None = None
        try:
            raw_socket.settimeout(min(5.0, self._remaining_seconds()))
            tls_socket = self.ssl_context.wrap_socket(raw_socket, server_hostname=host)
            target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            request = (
                f"GET {target} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Accept: {accept}\r\n"
                "User-Agent: AI-Price-Radar-Detector/1\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            tls_socket.sendall(request)
            response = http.client.HTTPResponse(tls_socket)
            response.begin()
            headers = {key.casefold(): value for key, value in response.getheaders()}
            if 300 <= response.status < 400:
                raise ValueError("source redirects are not followed")
            content_length = int(headers.get("content-length") or 0)
            limit = min(MAX_RESPONSE_BYTES, self.remaining_bytes)
            if content_length > limit:
                raise ValueError("source response exceeds size limit")
            chunks: list[bytes] = []
            total = 0
            while True:
                tls_socket.settimeout(min(5.0, self._remaining_seconds()))
                chunk = response.read(min(64 * 1024, limit - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError("source response exceeds size limit")
                chunks.append(chunk)
            self.remaining_bytes -= total
            return ProbeResponse(response.status, headers, b"".join(chunks))
        finally:
            if response is not None:
                response.close()
            if tls_socket is not None:
                tls_socket.close()
            else:
                raw_socket.close()


def _json(response: ProbeResponse) -> Any:
    if response.status != 200:
        raise ValueError(f"source returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("source did not return JSON")
    return json.loads(response.body.decode("utf-8"))


def _localized(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for key in ("zh-CN", "zh-TW", "en-US", "en", *sorted(str(item) for item in value)):
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def probe_source(value: object, *, client: PinnedHTTPSClient | None = None) -> ProbeResult:
    client = client or PinnedHTTPSClient()
    normalized = client.normalize_url(value)
    parsed = urllib.parse.urlsplit(normalized)
    host = parsed.hostname or ""
    match = LDXP_PATH.fullmatch(parsed.path.rstrip("/"))
    if host in LDXP_HOSTS and match:
        token = urllib.parse.unquote(match.group(1)).strip()
        source_url = f"https://pay.ldxp.cn/shop/{urllib.parse.quote(token, safe='._~-')}"
        return ProbeResult("ldxp", source_url, token.casefold())

    origin = urllib.parse.urlunsplit(("https", parsed.netloc, "", "", ""))
    try:
        config = _json(client.get(f"{origin}/api/v1/public/config", accept="application/json"))
        products = _json(client.get(
            f"{origin}/api/v1/public/products?page=1&page_size=1",
            accept="application/json",
        ))
        if (
            isinstance(config, dict)
            and config.get("status_code") == 0
            and isinstance(config.get("data"), dict)
            and isinstance(products, dict)
            and products.get("status_code") == 0
            and isinstance(products.get("data"), list)
            and isinstance(products.get("pagination"), dict)
        ):
            data = config["data"]
            brand = data.get("brand") if isinstance(data.get("brand"), dict) else {}
            shop_name = str(brand.get("site_name") or data.get("site_name") or host).strip()
            total = products["pagination"].get("total")
            product_count = int(total) if total not in (None, "") else len(products["data"])
            return ProbeResult("dujiao_next", origin, origin, shop_name, product_count)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    try:
        document = _json(client.get(normalized, accept="application/json"))
        items = document if isinstance(document, list) else document.get("items") if isinstance(document, dict) else None
        if isinstance(items, list) and all(isinstance(item, dict) for item in items):
            name = ""
            if isinstance(document, dict) and isinstance(document.get("shop"), dict):
                name = str(document["shop"].get("name") or "").strip()
            token = "feed-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
            return ProbeResult("merchant_json", normalized, normalized, name, len(items))
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    page = client.get(normalized, accept="text/html,application/xhtml+xml")
    if page.status != 200:
        raise ValueError(f"source returned HTTP {page.status}")
    token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return ProbeResult("other", normalized, normalized, host, 0)
