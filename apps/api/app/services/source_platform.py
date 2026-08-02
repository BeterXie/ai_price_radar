from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx


SOURCE_PLATFORM_LABELS = {
    "ldxp": "链动小铺",
    "dujiao_next": "Dujiao-Next",
    "merchant_json": "商家 Feed",
    "woocommerce": "WooCommerce",
    "schema_org": "独立站",
    "other": "其他独立站",
}

SOURCE_KIND_BY_PLATFORM = {
    "ldxp": "public_page",
    "dujiao_next": "public_api",
    "merchant_json": "public_feed",
    "woocommerce": "public_api",
    "schema_org": "structured_data",
    "other": "public_page",
}

SOURCE_KIND_LABELS = {
    "public_page": "公开页面",
    "public_api": "公开 API",
    "public_feed": "公开 Feed",
    "structured_data": "结构化数据",
}

PLATFORM_ALIASES = {
    "merchant_feed": "merchant_json",
}

LDXP_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"}
MAX_DETECTION_BYTES = 1024 * 1024


def canonical_source_platform(value: str) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    return PLATFORM_ALIASES.get(normalized, normalized)


def source_platform_label(value: str) -> str:
    platform = canonical_source_platform(value)
    return SOURCE_PLATFORM_LABELS.get(platform, SOURCE_PLATFORM_LABELS["other"])


def source_kind(value: str) -> str:
    return SOURCE_KIND_BY_PLATFORM.get(canonical_source_platform(value), "public_page")


def source_kind_label(value: str) -> str:
    return SOURCE_KIND_LABELS.get(value, value)


def workflow_status(value: str) -> str:
    return {
        "queued": "approved",
        "validating": "detecting",
        "validated": "approved",
        "onboarded": "published",
        "no_products": "validation_failed",
    }.get(value, value)


@dataclass(frozen=True, slots=True)
class SourceDetection:
    platform: str
    source_url: str
    source_key: str
    shop_token: str


def _normalized_https_url(value: object) -> str:
    parsed = urllib.parse.urlsplit(str(value))
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or parsed.username or parsed.password:
        raise ValueError("来源地址必须是公开 HTTPS URL")
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("来源地址不能指向本地或内部主机")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise ValueError("来源地址不能使用私有或保留 IP")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("来源地址端口无效") from exc
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = f"{rendered_host}:{port}" if port and port != 443 else rendered_host
    return urllib.parse.urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def _ldxp_detection(url: str) -> SourceDetection | None:
    parsed = urllib.parse.urlsplit(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.rstrip("/").split("/") if part]
    if (parsed.hostname or "").casefold() not in LDXP_HOSTS or len(parts) != 2 or parts[0].casefold() != "shop":
        return None
    token = parts[1].strip()
    if not token or len(token) > 128 or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-" for character in token):
        return None
    source_url = f"https://pay.ldxp.cn/shop/{urllib.parse.quote(token, safe='._~-')}"
    return SourceDetection("ldxp", source_url, token.casefold(), token)


def _ensure_public_host(url: str, resolver: Callable[..., list[tuple[Any, ...]]]) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    try:
        addresses = {item[4][0] for item in resolver(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError:
        return False
    if not addresses:
        return False
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("来源主机必须解析到公网地址")
    return True


def _fetch_json(url: str) -> Any:
    with httpx.Client(follow_redirects=False, timeout=5.0) as client:
        with client.stream("GET", url, headers={"Accept": "application/json", "User-Agent": "AI-Price-Radar-Intake/3.4"}) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").casefold()
            if content_type and "json" not in content_type:
                raise ValueError("来源未返回 JSON")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_DETECTION_BYTES:
                    raise ValueError("来源检测响应超过 1 MiB")
                chunks.append(chunk)
    return json.loads(b"".join(chunks).decode("utf-8"))


def _dujiao_contract(fetch_json: Callable[[str], Any], origin: str) -> bool:
    try:
        config = fetch_json(f"{origin}/api/v1/public/config")
        products = fetch_json(f"{origin}/api/v1/public/products?page=1&page_size=1")
    except Exception:
        return False
    return (
        isinstance(config, dict)
        and config.get("status_code") == 0
        and isinstance(config.get("data"), dict)
        and isinstance(products, dict)
        and products.get("status_code") == 0
        and isinstance(products.get("data"), list)
        and isinstance(products.get("pagination"), dict)
    )


def _merchant_contract(fetch_json: Callable[[str], Any], url: str) -> bool:
    try:
        document = fetch_json(url)
    except Exception:
        return False
    if isinstance(document, list):
        return all(isinstance(item, dict) for item in document)
    return isinstance(document, dict) and isinstance(document.get("items"), list) and all(
        isinstance(item, dict) for item in document["items"]
    )


def detect_source_platform(
    value: object,
    *,
    fetch_json: Callable[[str], Any] = _fetch_json,
    resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
) -> SourceDetection:
    raw = urllib.parse.urlsplit(str(value))
    if (
        raw.scheme.casefold() in {"http", "https"}
        and not raw.username
        and not raw.password
        and (raw.hostname or "").casefold().rstrip(".") in LDXP_HOSTS
    ):
        ldxp_url = urllib.parse.urlunsplit(("https", raw.netloc, raw.path, raw.query, ""))
        if ldxp := _ldxp_detection(ldxp_url):
            return ldxp
    normalized = _normalized_https_url(value)
    if ldxp := _ldxp_detection(normalized):
        return ldxp

    if not _ensure_public_host(normalized, resolver):
        token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
        return SourceDetection("other", normalized, normalized, token)
    parsed = urllib.parse.urlsplit(normalized)
    origin = urllib.parse.urlunsplit(("https", parsed.netloc, "", "", ""))
    if _dujiao_contract(fetch_json, origin):
        token = "dujiao-next-" + hashlib.sha256(origin.encode()).hexdigest()[:20]
        return SourceDetection("dujiao_next", origin, origin, token)
    if _merchant_contract(fetch_json, normalized):
        token = "feed-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
        return SourceDetection("merchant_json", normalized, normalized, token)
    token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return SourceDetection("other", normalized, normalized, token)
