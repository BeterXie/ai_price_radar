from __future__ import annotations

import hashlib
import json
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient

from currencies import normalize_currency

from .base import validate_record


name = "dujiao-next"
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 100
MAX_PRODUCTS = 2_000
PAGE_SIZE = 100


def _validate_public_url(value: str) -> urllib.parse.SplitResult:
    try:
        return urllib.parse.urlsplit(PinnedHTTPSClient.normalize_url(value))
    except ValueError as exc:
        raise ValueError("Dujiao-Next source must be a public HTTPS URL on port 443") from exc


def _validate_store_url(value: str) -> urllib.parse.SplitResult:
    parsed = _validate_public_url(value)
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Dujiao-Next source must be the shop root URL")
    return parsed


def _get_json(url: str, *, client: PinnedHTTPSClient | None = None) -> Any:
    client = client or PinnedHTTPSClient(
        max_response_bytes=MAX_BYTES,
        max_task_bytes=MAX_BYTES,
        max_task_seconds=60,
        request_timeout=20,
        user_agent="AI-Price-Radar-Importer/3.4",
    )
    response = client.get(url, accept="application/json")
    if response.status != 200:
        raise ValueError(f"Dujiao-Next API returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("Dujiao-Next API must return JSON content")
    return json.loads(response.body.decode("utf-8"))


def _origin(parsed: urllib.parse.SplitResult) -> str:
    return urllib.parse.urlunsplit(("https", parsed.netloc.casefold(), "", "", ""))


def _api_url(origin: str, path: str, query: dict[str, int] | None = None) -> str:
    url = f"{origin}/api/v1/public/{path.lstrip('/')}"
    return f"{url}?{urllib.parse.urlencode(query)}" if query else url


def _data(
    url: str,
    expected_type: type,
    *,
    client: PinnedHTTPSClient | None = None,
) -> tuple[Any, dict[str, Any]]:
    document = _get_json(url, client=client)
    if not isinstance(document, dict):
        raise ValueError("Dujiao-Next API response must be an object")
    if document.get("status_code") != 0:
        raise ValueError(f"Dujiao-Next API error: {document.get('msg') or document.get('status_code')}")
    data = document.get("data")
    if not isinstance(data, expected_type):
        raise ValueError("Dujiao-Next API returned invalid data")
    return data, document


def _pagination(document: dict[str, Any], expected_page: int, item_count: int) -> int:
    pagination = document.get("pagination")
    if not isinstance(pagination, dict):
        raise ValueError("Dujiao-Next product response missing pagination")
    try:
        page = int(pagination["page"])
        total_page = int(pagination["total_page"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Dujiao-Next product pagination is invalid") from exc
    empty_catalog = expected_page == 1 and total_page == 0 and item_count == 0
    if page != expected_page or total_page > MAX_PAGES or (not empty_catalog and total_page < expected_page):
        raise ValueError("Dujiao-Next product pagination is invalid")
    return total_page


def _localized(value: Any, preferred: Iterable[str] = ()) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    keys = [*preferred, "zh-CN", "zh-TW", "en-US", "en"]
    seen: set[str] = set()
    for key in [*keys, *sorted(str(item) for item in value)]:
        if key in seen:
            continue
        seen.add(key)
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _shop_name(config: dict[str, Any], hostname: str | None) -> str:
    brand = config.get("brand")
    brand = brand if isinstance(brand, dict) else {}
    return str(
        brand.get("site_name")
        or config.get("site_name")
        or hostname
        or "Dujiao-Next"
    ).strip()


def _stock(product: dict[str, Any], sku: dict[str, Any] | None = None) -> tuple[int | None, str]:
    item = sku or product
    if item.get("is_sold_out") is True or product.get("is_sold_out") is True:
        return 0, "out_of_stock"
    status = str(item.get("stock_status") or product.get("stock_status") or "").strip()
    if item.get("stock_quantity_hidden") is True or status == "unlimited":
        return None, status or "in_stock"

    fulfillment_type = str(product.get("fulfillment_type") or "")
    if sku is None:
        field = "auto_stock_available" if fulfillment_type == "auto" else "manual_stock_available"
        count = _integer(product.get(field))
    elif fulfillment_type == "auto":
        count = _integer(sku.get("auto_stock_available"))
    else:
        total = _integer(sku.get("manual_stock_total"))
        sold = _integer(sku.get("manual_stock_sold")) or 0
        count = None if total is None or total < 0 else max(0, total - sold)
    if count is not None:
        return count, "in_stock" if count > 0 else "out_of_stock"
    return None, status


def _record(
    *,
    origin: str,
    token: str,
    shop_name: str,
    currency: str,
    languages: list[str],
    categories: dict[str, str],
    product: dict[str, Any],
    sku: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slug = str(product.get("slug") or "").strip()
    title = _localized(product.get("title"), languages)
    variant_name = _localized(sku.get("spec_values"), languages) if sku else ""
    if sku and not variant_name:
        variant_name = str(sku.get("sku_code") or sku.get("id") or "").strip()
    product_name = f"{title} · {variant_name}" if variant_name else title
    category = product.get("category") if isinstance(product.get("category"), dict) else {}
    category_name = _localized(category.get("name"), languages) or categories.get(str(product.get("category_id") or ""), "")
    stock_count, stock_status = _stock(product, sku)
    raw_json = dict(product)
    raw_json["description"] = _localized(product.get("content"), languages) or _localized(product.get("description"), languages)
    if sku:
        raw_json["sku"] = sku
    price = sku.get("price_amount") if sku else product.get("price_amount")
    key = f"{slug}:sku:{sku.get('id')}" if sku else slug
    raw = {
        "token": token,
        "shop_name": shop_name,
        "shop_url": origin,
        "shop_status": "success",
        "source_platform": "dujiao_next",
        "source_kind": "public_api",
        "product_key": key,
        "variant_key": str(sku.get("sku_code") or sku.get("id") or "") if sku else "",
        "product_name": product_name,
        "category_name": category_name,
        "product_url": f"{origin}/products/{urllib.parse.quote(slug, safe='')}",
        "listed_price": price,
        "currency": currency,
        "stock_count": stock_count,
        "product_status": stock_status,
        "auto_delivery": str(product.get("fulfillment_type") or "") == "auto",
        "raw_json": raw_json,
    }
    return validate_record(raw)


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    parsed = _validate_store_url(str(source))
    origin = _origin(parsed)
    client = PinnedHTTPSClient(
        max_response_bytes=MAX_BYTES,
        max_task_bytes=30 * MAX_BYTES,
        max_task_seconds=120,
        request_timeout=20,
        user_agent="AI-Price-Radar-Importer/3.4",
    )

    probe_items, probe = _data(_api_url(origin, "products", {"page": 1, "page_size": 1}), list, client=client)
    _pagination(probe, 1, len(probe_items))

    config, _ = _data(_api_url(origin, "config"), dict, client=client)
    currency = normalize_currency(config.get("currency"))
    languages = [str(value) for value in config.get("languages", []) if str(value).strip()] if isinstance(config.get("languages"), list) else []
    shop_name = _shop_name(config, parsed.hostname)
    token = "dujiao-next-" + hashlib.sha256(origin.encode()).hexdigest()[:20]

    category_items, _ = _data(_api_url(origin, "categories"), list, client=client)
    categories = {
        str(item.get("id")): _localized(item.get("name"), languages)
        for item in category_items
        if isinstance(item, dict) and item.get("id") is not None
    }

    product_count = 0
    seen_slugs: set[str] = set()
    page = 1
    while True:
        items, document = _data(
            _api_url(origin, "products", {"page": page, "page_size": PAGE_SIZE}),
            list,
            client=client,
        )
        total_page = _pagination(document, page, len(items))
        for summary in items:
            if not isinstance(summary, dict):
                raise ValueError("Dujiao-Next product must be an object")
            slug = str(summary.get("slug") or "").strip()
            if not slug or slug in seen_slugs:
                raise ValueError("Dujiao-Next product slug is missing or duplicated")
            seen_slugs.add(slug)
            product_count += 1
            if product_count > MAX_PRODUCTS:
                raise ValueError("Dujiao-Next source exceeds 2000 products")
            detail, _ = _data(
                _api_url(origin, f"products/{urllib.parse.quote(slug, safe='')}"),
                dict,
                client=client,
            )
            if str(detail.get("slug") or "").strip() != slug:
                raise ValueError("Dujiao-Next product detail slug mismatch")
            product = {**summary, **detail}
            skus = product.get("skus")
            if isinstance(skus, list) and skus:
                for sku in skus:
                    if not isinstance(sku, dict):
                        raise ValueError("Dujiao-Next SKU must be an object")
                    if sku.get("is_active") is False:
                        continue
                    if sku.get("id") in (None, ""):
                        raise ValueError("Dujiao-Next SKU missing id")
                    yield _record(
                        origin=origin,
                        token=token,
                        shop_name=shop_name,
                        currency=currency,
                        languages=languages,
                        categories=categories,
                        product=product,
                        sku=sku,
                    )
            else:
                yield _record(
                    origin=origin,
                    token=token,
                    shop_name=shop_name,
                    currency=currency,
                    languages=languages,
                    categories=categories,
                    product=product,
                )
        if page >= total_page:
            break
        page += 1
