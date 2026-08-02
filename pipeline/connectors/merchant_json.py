from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from currencies import normalize_currency

from .base import validate_record


name = "merchant-json"
MAX_BYTES = 5 * 1024 * 1024


def _validate_remote_url(value: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("merchant feed URL must be a public HTTPS URL")
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("merchant feed host must be public")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("merchant feed host could not be resolved") from exc
    if not addresses:
        raise ValueError("merchant feed host did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("merchant feed host resolves to a non-public address")
    return parsed


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, "merchant feed redirects are disabled", headers, fp)


def _read_source(source: str | Path) -> tuple[bytes, str]:
    value = str(source)
    path = Path(value)
    if path.is_file():
        payload = path.read_bytes()
        if len(payload) > MAX_BYTES:
            raise ValueError("merchant feed exceeds 5 MiB")
        return payload, path.resolve().as_uri()

    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme:
        _validate_remote_url(value)
        request = urllib.request.Request(value, headers={"User-Agent": "AI-Price-Radar-Importer/3.2", "Accept": "application/json"})
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=20) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "json" not in content_type:
                raise ValueError("merchant feed must return JSON content")
            if int(response.headers.get("Content-Length") or 0) > MAX_BYTES:
                raise ValueError("merchant feed exceeds 5 MiB")
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError("merchant feed exceeds 5 MiB")
            return payload, value
    payload = path.read_bytes()
    if len(payload) > MAX_BYTES:
        raise ValueError("merchant feed exceeds 5 MiB")
    return payload, path.resolve().as_uri()


def _items(document: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)], {}
    if isinstance(document, dict):
        values = document.get("items")
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)], document
    raise ValueError("merchant feed must be a JSON array or an object containing an items array")


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    payload, source_url = _read_source(source)
    document = json.loads(payload.decode("utf-8"))
    items, metadata = _items(document)
    shop = metadata.get("shop") if isinstance(metadata.get("shop"), dict) else {}
    shop_url = str(shop.get("url") or metadata.get("shop_url") or source_url)
    shop_name = str(shop.get("name") or metadata.get("shop_name") or urllib.parse.urlsplit(shop_url).hostname or "Merchant feed")
    token = str(shop.get("token") or metadata.get("shop_token") or "").strip()
    if not token:
        token = "feed-" + hashlib.sha256(shop_url.encode()).hexdigest()[:20]

    for index, item in enumerate(items):
        product_url = str(item.get("url") or item.get("product_url") or "").strip()
        product_name = str(item.get("name") or item.get("product_name") or "").strip()
        key = str(item.get("id") or item.get("sku") or item.get("product_key") or product_url or f"item-{index}")
        raw = {
            "token": token,
            "shop_name": shop_name,
            "shop_url": shop_url,
            "shop_status": "success",
            "source_platform": "merchant_json",
            "product_key": key,
            "product_name": product_name,
            "category_name": item.get("category") or item.get("category_name") or "",
            "product_url": product_url,
            "listed_price": item.get("price"),
            "currency": normalize_currency(item.get("currency")),
            "stock_count": item.get("stock_count") if item.get("stock_count") not in (None, "") else item.get("stock"),
            "product_status": item.get("stock_status") or item.get("status") or "",
            "auto_delivery": item.get("auto_delivery"),
            "collected_at": item.get("observed_at") or metadata.get("updated_at"),
            "raw_json": item,
        }
        yield validate_record(raw)
