from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient

from .base import validate_record


name = "16688"
HOSTS = {"16688.com.cn", "www.16688.com.cn"}
SHOP_PATH = re.compile(r"^/shop/([A-Za-z0-9._~-]+)$", re.IGNORECASE)
CODE_PATTERN = re.compile(r"[A-Za-z0-9._~-]{1,128}")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
SHOP_DETAIL_PATH = "/shopApi/shop/detail"
GOODS_LIST_PATH = "/shopApi/goods/list"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_TASK_SECONDS = 120
REQUEST_TIMEOUT = 20


def _validate_store_url(value: str) -> tuple[urllib.parse.SplitResult, str]:
    raw = str(value or "")
    if not raw or raw != raw.strip() or CONTROL_CHARACTERS.search(raw) or "#" in raw:
        raise ValueError("16688 source must be a public shop URL")
    try:
        parsed = urllib.parse.urlsplit(PinnedHTTPSClient.normalize_url(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError("16688 source must be a public HTTPS shop URL") from exc
    host = (parsed.hostname or "").casefold()
    match = SHOP_PATH.fullmatch(parsed.path.rstrip("/"))
    if host not in HOSTS or match is None or parsed.query or parsed.fragment:
        raise ValueError("16688 source must be an official /shop/{code} URL")
    shop_no = urllib.parse.unquote(match.group(1)).strip()
    if CODE_PATTERN.fullmatch(shop_no) is None:
        raise ValueError("16688 shop code is invalid")
    normalized_path = f"/shop/{urllib.parse.quote(shop_no, safe='._~-')}"
    return parsed._replace(path=normalized_path), shop_no


def _origin(parsed: urllib.parse.SplitResult) -> str:
    return urllib.parse.urlunsplit(("https", (parsed.hostname or "").casefold(), "", "", ""))


def _post_json(
    client: PinnedHTTPSClient,
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = client.post_json(url, payload)
    if response.status != 200:
        raise ValueError(f"16688 API returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("16688 API must return JSON content")
    try:
        document = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("16688 API returned invalid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("16688 API response must be an object")
    if document.get("code") != 1:
        raise ValueError(f"16688 API error: {document.get('msg') or document.get('code')}")
    return document


def _shop_token(shop_no: str) -> str:
    return f"16688-{shop_no}"


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _stock(item: dict[str, Any]) -> tuple[int | None, str]:
    count = _integer(item.get("stock_available_quantity"))
    source_status = str(item.get("stock_available_status") or "").strip().casefold()
    if source_status == "out" or count == 0:
        return 0, "out_of_stock"
    if count is not None and count > 0:
        return count, "in_stock"
    return None, source_status or "unknown"


def _record(
    *,
    origin: str,
    shop_no: str,
    shop_name: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    goods_no = str(item.get("goods_no") or "").strip()
    product_name = str(item.get("name") or "").strip()
    if CODE_PATTERN.fullmatch(goods_no) is None:
        raise ValueError("16688 goods number is missing or invalid")
    if not product_name:
        raise ValueError("16688 goods name is missing")
    stock_count, product_status = _stock(item)
    raw_json = dict(item)
    raw_json["description"] = str(item.get("description") or "")
    raw_json["16688_shop_no"] = shop_no
    return validate_record({
        "token": _shop_token(shop_no),
        "shop_name": shop_name,
        "shop_url": f"{origin}/shop/{urllib.parse.quote(shop_no, safe='._~-')}",
        "shop_status": "success",
        "source_platform": "16688",
        "source_kind": "public_api",
        "product_key": f"16688:{goods_no}",
        "variant_key": goods_no,
        "product_name": product_name,
        "category_name": "",
        "product_url": f"{origin}/goods/{urllib.parse.quote(goods_no, safe='._~-')}",
        "listed_price": item.get("price"),
        "currency": "CNY",
        "stock_count": stock_count,
        "product_status": product_status,
        "auto_delivery": None,
        "raw_json": raw_json,
    })


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    parsed, requested_shop_no = _validate_store_url(str(source))
    origin = _origin(parsed)
    client = PinnedHTTPSClient(
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_task_bytes=MAX_TOTAL_BYTES,
        max_task_seconds=MAX_TASK_SECONDS,
        request_timeout=REQUEST_TIMEOUT,
        user_agent="AI-Price-Radar-Importer/1",
    )

    detail = _post_json(
        client,
        f"{origin}{SHOP_DETAIL_PATH}",
        {"shop_no": requested_shop_no},
    )
    shop = detail.get("data")
    if not isinstance(shop, dict):
        raise ValueError("16688 shop detail is missing")
    shop_no = str(shop.get("shop_no") or requested_shop_no).strip()
    if CODE_PATTERN.fullmatch(shop_no) is None:
        raise ValueError("16688 shop detail returned an invalid shop number")
    shop_name = str(shop.get("name") or shop_no).strip()
    if not shop_name:
        shop_name = shop_no

    listing = _post_json(
        client,
        f"{origin}{GOODS_LIST_PATH}",
        {"shop_no": shop_no, "sort": "default"},
    )
    data = listing.get("data")
    items = data.get("list") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("16688 goods API response is missing a list")

    seen_goods: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("16688 goods item must be an object")
        goods_no = str(item.get("goods_no") or "").strip()
        if goods_no in seen_goods:
            raise ValueError("16688 goods list contains a duplicate goods number")
        seen_goods.add(goods_no)
        yield _record(origin=origin, shop_no=shop_no, shop_name=shop_name, item=item)
