from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient

from .base import SourceFetchError, validate_record


name = "kmdian"
API_URL = "https://www.kmdian.com/api/v1/open/products"
API_KEY_ENV = "KMDIAN_API_KEY"
PAGE_SIZE = 20
MAX_PAGES = 500
REQUEST_INTERVAL_SECONDS = 1.1  # Below the platform's 60 requests/minute/key limit.
CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,100}")
RAW_FIELDS = frozenset({
    "shop_name", "shop_url", "shop_code", "goods_no", "title", "product_url",
    "price_cent", "stock", "sales_count", "cover", "updated_at",
})


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError(f"kmdian {field} must be an integer")
    result = int(value)
    if result < minimum:
        raise ValueError(f"kmdian {field} must be at least {minimum}")
    return result


def _record(item: Any, *, api_key: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("kmdian product must be an object")
    for field in ("shop_code", "goods_no"):
        if not isinstance(item.get(field), str) or CODE_PATTERN.fullmatch(item[field]) is None:
            raise ValueError(f"kmdian {field} is missing or invalid")
    for field in ("shop_name", "title", "shop_url", "product_url"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"kmdian {field} is missing or invalid")
    stock = None if item.get("stock") is None else _integer(item["stock"], "stock")
    price_cent = _integer(item.get("price_cent"), "price_cent")
    encoded_item = json.dumps(item, ensure_ascii=False, default=str)
    if api_key in encoded_item:
        raise ValueError("kmdian response contains the API credential")
    raw_json = {key: item[key] for key in RAW_FIELDS if key in item}
    return validate_record({
        "token": f"kmdian-{item['shop_code']}",
        "shop_name": item["shop_name"].strip(),
        "shop_url": PinnedHTTPSClient.normalize_url(item["shop_url"]),
        "shop_status": "success",
        "source_platform": name,
        "source_kind": "platform_api",
        "product_key": f"kmdian:{item['goods_no']}",
        "variant_key": item["goods_no"],
        "product_name": item["title"].strip(),
        "product_url": PinnedHTTPSClient.normalize_url(item["product_url"]),
        "listed_price": Decimal(price_cent) / 100,
        "currency": "CNY",
        "stock_count": stock,
        "product_status": "unknown" if stock is None else "in_stock" if stock > 0 else "out_of_stock",
        "auto_delivery": None,
        # Preserve sales_count, cover and source updated_at. The current request,
        # not the last product edit, determines observation freshness.
        "raw_json": raw_json,
    })


def _page(client: PinnedHTTPSClient, api_key: str, page: int) -> dict[str, Any]:
    try:
        response = client.get(
            f"{API_URL}?page={page}&per_page={PAGE_SIZE}",
            accept="application/json",
            headers={"X-Api-Key": api_key},
        )
    except ssl.SSLCertVerificationError:
        raise
    except (OSError, http.client.HTTPException):
        raise SourceFetchError("kmdian API request failed") from None
    if response.status in (401, 403):
        raise ValueError("kmdian API access denied: check KMDIAN_API_KEY and the collector IP whitelist")
    if response.status == 408:
        raise SourceFetchError("kmdian API request timeout (HTTP 408)")
    if response.status == 429:
        raise SourceFetchError("kmdian API rate limit exceeded (60 requests/minute/key)")
    if response.status >= 500:
        raise SourceFetchError(f"kmdian API returned HTTP {response.status}")
    if response.status != 200:
        raise ValueError(f"kmdian API returned HTTP {response.status}")
    try:
        document = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("kmdian API returned invalid JSON") from None
    if not isinstance(document, dict) or type(document.get("code")) is not int or document["code"] != 0:
        # Do not echo upstream error bodies: they may contain credentials.
        raise ValueError("kmdian API reported an unsuccessful response")
    data = document.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list) or not isinstance(data.get("pagination"), dict):
        raise ValueError("kmdian API response is missing list or pagination")
    return data


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    # The credential is only ever sent to this fixed endpoint; no configurable
    # hosts, product requests or pagination links can receive it.
    if str(source) != API_URL:
        raise ValueError(f"kmdian source must be {API_URL}")
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise ValueError("KMDIAN_API_KEY is required (app_id.secret)")
    if not api_key.isascii() or any(ord(ch) < 33 or ord(ch) == 127 for ch in api_key) or "." not in api_key:
        raise ValueError("KMDIAN_API_KEY must contain a valid app_id.secret")
    client = PinnedHTTPSClient(
        max_response_bytes=5 * 1024 * 1024,
        max_task_bytes=50 * 1024 * 1024,
        max_task_seconds=600,
        request_timeout=20,
        user_agent="AI-Price-Radar-Importer/1",
    )
    next_request_at = time.monotonic()

    def read_pass() -> list[dict[str, Any]]:
        nonlocal next_request_at
        seen: set[tuple[str, str]] = set()
        expected_pagination: tuple[int, int, int] | None = None
        records: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            delay = next_request_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            next_request_at = time.monotonic() + REQUEST_INTERVAL_SECONDS
            data = _page(client, api_key, page)
            observed_at = datetime.now(timezone.utc)
            pagination = data["pagination"]
            current_page = _integer(pagination.get("page"), "pagination.page", minimum=1)
            per_page = _integer(pagination.get("per_page"), "pagination.per_page", minimum=1)
            total = _integer(pagination.get("total"), "pagination.total")
            last_page = _integer(pagination.get("last_page"), "pagination.last_page")
            if current_page != page or per_page > PAGE_SIZE or last_page > MAX_PAGES:
                raise ValueError("kmdian API returned invalid pagination or exceeded the page limit")
            expected_last_page = (total + per_page - 1) // per_page
            if last_page != expected_last_page and not (total == 0 and last_page == 1):
                raise ValueError("kmdian API pagination does not match its total")
            signature = (per_page, total, last_page)
            if expected_pagination is not None and signature != expected_pagination:
                raise ValueError("kmdian catalog changed during pagination; retry the complete import")
            expected_pagination = signature
            expected_count = min(per_page, max(0, total - (page - 1) * per_page))
            if len(data["list"]) != expected_count:
                raise ValueError("kmdian API returned an incomplete page")
            for item in data["list"]:
                record = _record(item, api_key=api_key)
                identity = (record["token"], record["product_key"])
                if identity in seen:
                    raise ValueError("kmdian API repeated a product during pagination")
                seen.add(identity)
                record["observed_at"] = observed_at
                records.append(record)
            if page >= last_page:
                return records
        raise ValueError("kmdian API exceeded the page limit")

    first_pass = read_pass()
    # The API exposes no snapshot/version token. For a multi-page response,
    # read it twice and only permit stale-offer pruning when the complete
    # product identity set agrees across both passes.
    if len(first_pass) <= PAGE_SIZE:
        yield from first_pass
        return
    second_pass = read_pass()
    first_ids = {(row["token"], row["product_key"]) for row in first_pass}
    second_ids = {(row["token"], row["product_key"]) for row in second_pass}
    if first_ids != second_ids:
        raise ValueError("kmdian catalog changed during pagination; retry the complete import")
    yield from second_pass
