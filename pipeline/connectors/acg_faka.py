from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient

from currencies import normalize_currency

from .base import validate_record

name = "acg-faka"
MAX_BYTES = 5 * 1024 * 1024
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _validate_public_url(value: str) -> urllib.parse.SplitResult:
    try:
        return urllib.parse.urlsplit(PinnedHTTPSClient.normalize_url(value))
    except ValueError as exc:
        raise ValueError("ACG-Faka source must be a public HTTPS URL on port 443") from exc


def _validate_store_url(value: str) -> urllib.parse.SplitResult:
    parsed = _validate_public_url(value)
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("ACG-Faka source must be the shop root URL")
    return parsed


def _origin(parsed: urllib.parse.SplitResult) -> str:
    return urllib.parse.urlunsplit(("https", (parsed.hostname or "").casefold(), "", "", ""))


def _get_json(url: str, *, client: PinnedHTTPSClient) -> Any:
    response = client.get(url, accept="application/json")
    if response.status != 200:
        raise ValueError(f"ACG-Faka API returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("ACG-Faka API must return JSON content")
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("ACG-Faka API returned invalid JSON") from exc


def _extract_shop_name(origin: str, hostname: str, client: PinnedHTTPSClient) -> str:
    try:
        page = client.get(origin, accept="text/html,application/xhtml+xml")
        if page.status == 200:
            match = TITLE_PATTERN.search(page.body.decode("utf-8", errors="replace"))
            if match:
                raw_title = match.group(1).strip()
                parts = [p.strip() for p in raw_title.split("-") if p.strip()]
                for part in reversed(parts):
                    if part not in {"购物", "首页", "Home", "Shop", "商城"}:
                        return part
                return raw_title
    except Exception:
        pass
    return hostname


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    parsed = _validate_store_url(str(source))
    origin = _origin(parsed)
    hostname = (parsed.hostname or "").casefold()
    token = f"acg-faka-{hashlib.sha256(origin.encode('utf-8')).hexdigest()[:24]}"

    client = PinnedHTTPSClient(
        max_response_bytes=MAX_BYTES,
        max_task_bytes=20 * MAX_BYTES,
        max_task_seconds=60,
        request_timeout=20,
        user_agent="AI-Price-Radar-Importer/3.4",
    )

    shop_name = _extract_shop_name(origin, hostname, client)

    # 1. Fetch categories
    category_map: dict[int, str] = {}
    try:
        cat_doc = _get_json(f"{origin}/user/api/index/data", client=client)
        if isinstance(cat_doc, dict) and cat_doc.get("code") == 200:
            cat_list = cat_doc.get("data")
            if isinstance(cat_list, list):
                for cat in cat_list:
                    if isinstance(cat, dict) and "id" in cat and "name" in cat:
                        category_map[int(cat["id"])] = str(cat["name"]).strip()
    except Exception:
        pass

    # 2. Fetch commodities
    com_doc = _get_json(f"{origin}/user/api/index/commodity", client=client)
    if not isinstance(com_doc, dict) or com_doc.get("code") != 200:
        msg = com_doc.get("msg") if isinstance(com_doc, dict) else "unknown"
        raise ValueError(f"ACG-Faka commodity API returned error: {msg}")

    items = com_doc.get("data")
    if not isinstance(items, list):
        raise ValueError("ACG-Faka commodity API data is not a list")

    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id in (None, ""):
            continue

        product_name = str(item.get("name") or "").strip()
        if not product_name:
            continue

        raw_price = item.get("price")
        try:
            price = Decimal(str(raw_price)) if raw_price not in (None, "") else None
        except (InvalidOperation, ValueError):
            price = None

        raw_stock = item.get("stock")
        try:
            stock_count = int(raw_stock) if raw_stock not in (None, "") else None
        except (TypeError, ValueError):
            stock_count = None

        is_hidden = bool(item.get("hide"))
        is_disabled = item.get("status") not in (None, 1, "1")

        if is_hidden or is_disabled:
            stock_status = "unavailable"
        elif stock_count is not None and stock_count <= 0:
            stock_status = "out_of_stock"
        else:
            stock_status = "in_stock"

        cat_id = item.get("category_id")
        category_name = category_map.get(int(cat_id), "") if cat_id not in (None, "") else ""

        product_url = f"{origin}/item/{item_id}"
        auto_delivery = (item.get("delivery_way") == 0)

        record = {
            "token": token,
            "shop_name": shop_name,
            "shop_url": origin,
            "shop_status": "success",
            "source_platform": "acg_faka",
            "source_kind": "public_api",
            "product_key": str(item_id),
            "product_name": product_name,
            "category_name": category_name,
            "product_url": product_url,
            "listed_price": price,
            "currency": normalize_currency(item.get("currency") or "CNY"),
            "stock_count": stock_count,
            "product_status": stock_status,
            "auto_delivery": auto_delivery,
            "raw_json": item,
        }
        yield validate_record(record)
