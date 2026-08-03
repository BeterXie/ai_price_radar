from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient

from currencies import normalize_currency

from .base import validate_record


name = "merchant-json"
MAX_BYTES = 5 * 1024 * 1024
UPSTREAM_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")


def _validate_remote_url(value: str) -> urllib.parse.SplitResult:
    try:
        return urllib.parse.urlsplit(PinnedHTTPSClient.normalize_url(value))
    except ValueError as exc:
        raise ValueError("merchant feed URL must be public HTTPS on port 443") from exc


def _validate_public_link(value: object, field: str) -> str:
    raw = str(value or "")
    if not raw or raw != raw.strip():
        raise ValueError(f"merchant feed {field} must be an absolute public HTTPS URL")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise ValueError(f"merchant feed {field} must not contain control characters")
    if "#" in raw:
        raise ValueError(f"merchant feed {field} must not contain a fragment")
    try:
        return PinnedHTTPSClient.normalize_url(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"merchant feed {field} must be an absolute public HTTPS URL on port 443"
        ) from exc


def _internal_shop_token(source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
    return f"merchant-json-{digest}"


def _upstream_shop_token(shop: dict[str, Any], metadata: dict[str, Any]) -> str:
    value = str(shop.get("token") or metadata.get("shop_token") or "").strip()
    if value and UPSTREAM_TOKEN_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "merchant feed shop token must be 1-128 ASCII letters, digits, dots, underscores, colons, or hyphens"
        )
    return value


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
        normalized = _validate_remote_url(value).geturl()
        client = PinnedHTTPSClient(
            max_response_bytes=MAX_BYTES,
            max_task_bytes=MAX_BYTES,
            max_task_seconds=30,
            request_timeout=20,
            user_agent="AI-Price-Radar-Importer/3.4",
        )
        response = client.get(normalized, accept="application/json")
        if response.status != 200:
            raise ValueError(f"merchant feed returned HTTP {response.status}")
        content_type = response.headers.get("content-type", "").casefold()
        if content_type and "json" not in content_type:
            raise ValueError("merchant feed must return JSON content")
        return response.body, normalized
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
    shop_url = _validate_public_link(
        shop.get("url") or metadata.get("shop_url") or source_url,
        "shop URL",
    )
    shop_name = str(shop.get("name") or metadata.get("shop_name") or urllib.parse.urlsplit(shop_url).hostname or "Merchant feed")
    token = _internal_shop_token(source_url)
    upstream_shop_token = _upstream_shop_token(shop, metadata)

    for index, item in enumerate(items):
        product_url = _validate_public_link(
            item.get("url") or item.get("product_url"),
            f"item {index} product URL",
        )
        product_name = str(item.get("name") or item.get("product_name") or "").strip()
        key = str(item.get("id") or item.get("sku") or item.get("product_key") or product_url or f"item-{index}")
        raw_json = dict(item)
        source_updated_at = item.get("observed_at") or metadata.get("updated_at")
        if source_updated_at not in (None, ""):
            raw_json["source_updated_at"] = source_updated_at
        if upstream_shop_token:
            raw_json["upstream_shop_token"] = upstream_shop_token
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
            "raw_json": raw_json,
        }
        yield validate_record(raw)
