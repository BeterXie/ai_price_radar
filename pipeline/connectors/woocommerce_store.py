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


name = "woocommerce-store"
API_PATH = "/wp-json/wc/store/v1/products"
PAGE_SIZE = 100
MAX_PAGES = 100
MAX_PRODUCTS = 2_000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_TASK_SECONDS = 120
REQUEST_TIMEOUT = 20
MONEY_PATTERN = re.compile(r"[0-9]+")


def _validate_store_url(value: str) -> urllib.parse.SplitResult:
    raw = str(value or "")
    if not raw or raw != raw.strip() or "#" in raw:
        raise ValueError("WooCommerce source must be the public HTTPS shop root on port 443")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise ValueError("WooCommerce source must be the public HTTPS shop root on port 443")
    try:
        parsed = urllib.parse.urlsplit(PinnedHTTPSClient.normalize_url(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "WooCommerce source must be the public HTTPS shop root on port 443"
        ) from exc
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("WooCommerce source must be the public HTTPS shop root on port 443")
    return parsed


def _origin(parsed: urllib.parse.SplitResult) -> str:
    return urllib.parse.urlunsplit(("https", parsed.netloc.casefold(), "", "", ""))


def _safe_public_link(value: object) -> str:
    raw = str(value or "")
    if not raw or raw != raw.strip() or "#" in raw:
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        return ""
    try:
        return PinnedHTTPSClient.normalize_url(raw)
    except (TypeError, ValueError):
        return ""


def _required_public_link(value: object, field: str) -> str:
    link = _safe_public_link(value)
    if not link:
        raise ValueError(
            f"WooCommerce {field} must be an absolute public HTTPS URL on port 443 without credentials or fragments"
        )
    return link


def _api_url(origin: str, page: int, product_type: str | None = None) -> str:
    query: dict[str, str | int] = {"page": page, "per_page": PAGE_SIZE}
    if product_type:
        query["type"] = product_type
    return f"{origin}{API_PATH}?{urllib.parse.urlencode(query)}"


def _header_integer(headers: dict[str, str], field: str) -> int:
    value = headers.get(field)
    if value is None or not str(value).strip().isdigit():
        raise ValueError(f"WooCommerce Store API response missing or invalid {field} header")
    return int(str(value).strip())


def _product_id(product: dict[str, Any]) -> int:
    value = product.get("id")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("WooCommerce Store API product id is invalid")
    return value


def _json_response(response: Any) -> list[dict[str, Any]]:
    if response.status != 200:
        raise ValueError(f"WooCommerce Store API returned HTTP {response.status}")
    headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
    content_type = headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("WooCommerce Store API must return JSON content")
    try:
        document = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("WooCommerce Store API returned invalid JSON") from exc
    if not isinstance(document, list):
        raise ValueError("WooCommerce Store API product response must be an array")
    if any(not isinstance(item, dict) for item in document):
        raise ValueError("WooCommerce Store API product must be an object")
    return document


def _fetch_collection(
    origin: str,
    *,
    client: PinnedHTTPSClient,
    product_type: str | None = None,
    capacity: int,
) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    expected_total: int | None = None
    expected_pages: int | None = None
    page = 1

    while True:
        response = client.get(
            _api_url(origin, page, product_type),
            accept="application/json",
        )
        items = _json_response(response)
        headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
        total = _header_integer(headers, "x-wp-total")
        total_pages = _header_integer(headers, "x-wp-totalpages")

        calculated_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        if total_pages != calculated_pages or total_pages > MAX_PAGES:
            raise ValueError("WooCommerce Store API pagination is invalid or exceeds the page limit")
        if total > capacity:
            raise ValueError("WooCommerce source exceeds the 2000 product limit")
        if expected_total is None:
            expected_total = total
            expected_pages = total_pages
        elif total != expected_total or total_pages != expected_pages:
            raise ValueError("WooCommerce Store API pagination changed during collection")

        page_offset = (page - 1) * PAGE_SIZE
        expected_count = max(0, min(PAGE_SIZE, total - page_offset))
        if len(items) != expected_count:
            raise ValueError("WooCommerce Store API returned incomplete pagination")

        for item in items:
            item_id = _product_id(item)
            if item_id in seen_ids:
                raise ValueError("WooCommerce Store API returned a duplicate product id")
            seen_ids.add(item_id)
            products.append(item)

        if expected_pages is None or page >= expected_pages:
            break
        page += 1

    if expected_total is None or len(products) != expected_total:
        raise ValueError("WooCommerce Store API returned incomplete pagination")
    return products


def _minor_amount(value: object, minor_unit: int, field: str) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"WooCommerce {field} must use integer minor units")
    text = str(value)
    if text != text.strip() or MONEY_PATTERN.fullmatch(text) is None:
        raise ValueError(f"WooCommerce {field} must use integer minor units")
    digits = text.lstrip("0") or "0"
    if minor_unit == 0:
        return digits
    padded = digits.zfill(minor_unit + 1)
    return f"{padded[:-minor_unit]}.{padded[-minor_unit:]}"


def _price_data(product: dict[str, Any], *, require_complete: bool = False) -> dict[str, Any]:
    prices = product.get("prices")
    if not isinstance(prices, dict):
        raise ValueError("WooCommerce Store API product prices are invalid")
    minor_unit = prices.get("currency_minor_unit")
    if isinstance(minor_unit, bool) or not isinstance(minor_unit, int) or not 0 <= minor_unit <= 12:
        raise ValueError("WooCommerce currency_minor_unit is invalid")
    currency = normalize_currency(prices.get("currency_code"))
    current_price = _minor_amount(prices.get("price"), minor_unit, "current price")
    regular_price = _minor_amount(prices.get("regular_price"), minor_unit, "regular price")
    sale_price = _minor_amount(prices.get("sale_price"), minor_unit, "sale price")
    if require_complete and (current_price is None or regular_price is None):
        raise ValueError("WooCommerce variation price is incomplete")

    price_range = prices.get("price_range")
    normalized_range: dict[str, str | None] | None = None
    if price_range is not None:
        if not isinstance(price_range, dict):
            raise ValueError("WooCommerce product price range is invalid")
        normalized_range = {
            "min_amount": _minor_amount(price_range.get("min_amount"), minor_unit, "minimum price"),
            "max_amount": _minor_amount(price_range.get("max_amount"), minor_unit, "maximum price"),
        }

    return {
        "currency": currency,
        "minor_unit": minor_unit,
        "current_price": current_price,
        "regular_price": regular_price,
        "sale_price": sale_price,
        "price_range": normalized_range,
    }


def _categories(product: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    values = product.get("categories", [])
    if not isinstance(values, list):
        raise ValueError("WooCommerce product categories are invalid")
    names: list[str] = []
    categories: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("WooCommerce product category must be an object")
        category: dict[str, Any] = {}
        for field in ("id", "name", "slug"):
            if value.get(field) not in (None, ""):
                category[field] = value[field]
        name_value = str(value.get("name") or "").strip()
        if name_value:
            names.append(name_value)
        if value.get("link") not in (None, ""):
            link = _safe_public_link(value.get("link"))
            if link:
                category["link"] = link
        categories.append(category)
    return " / ".join(names), categories


def _images(product: dict[str, Any]) -> list[dict[str, Any]]:
    values = product.get("images", [])
    if not isinstance(values, list):
        raise ValueError("WooCommerce product images are invalid")
    images: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("WooCommerce product image must be an object")
        image: dict[str, Any] = {}
        for field in ("id", "name", "alt"):
            if value.get(field) not in (None, ""):
                image[field] = value[field]
        for field in ("src", "thumbnail"):
            if value.get(field) not in (None, ""):
                link = _safe_public_link(value.get(field))
                if link:
                    image[field] = link
        images.append(image)
    return images


def _boolean(product: dict[str, Any], field: str) -> bool | None:
    value = product.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"WooCommerce {field} must be a boolean")
    return value


def _stock(product: dict[str, Any]) -> tuple[int | None, str, bool | None, str]:
    is_in_stock = _boolean(product, "is_in_stock")
    is_on_backorder = _boolean(product, "is_on_backorder")
    is_purchasable = _boolean(product, "is_purchasable")

    if is_purchasable is False:
        stock_count = 0
        stock_status = "unavailable"
    elif is_in_stock is False:
        stock_count = 0
        stock_status = "out_of_stock"
    else:
        remaining = product.get("low_stock_remaining")
        stock_count = None
        if isinstance(remaining, int) and not isinstance(remaining, bool) and remaining >= 0:
            stock_count = remaining
        elif isinstance(remaining, str) and remaining.isdigit():
            stock_count = int(remaining)
        stock_status = (
            "on_backorder"
            if is_on_backorder is True
            else "in_stock"
            if is_in_stock is True
            else ""
        )
    purchase_status = (
        "purchasable"
        if is_purchasable is True
        else "not_purchasable"
        if is_purchasable is False
        else ""
    )
    return stock_count, stock_status, is_purchasable, purchase_status


def _shop_token(origin: str) -> str:
    digest = hashlib.sha256(origin.encode("utf-8")).hexdigest()[:20]
    return f"woocommerce-store-{digest}"


def _record(
    *,
    origin: str,
    token: str,
    shop_name: str,
    product: dict[str, Any],
    category_product: dict[str, Any] | None = None,
    parent_id: int | None = None,
    variant_label: str = "",
    variant_attributes: list[dict[str, str]] | None = None,
    require_complete_price: bool = False,
) -> dict[str, Any]:
    item_id = _product_id(product)
    base_product = category_product or product
    base_name = str(base_product.get("name") or "").strip()
    product_name = f"{base_name} · {variant_label}" if variant_label else base_name
    permalink = _required_public_link(product.get("permalink"), "product permalink")
    prices = _price_data(product, require_complete=require_complete_price)
    category_name, categories = _categories(base_product)
    images = _images(product)
    stock_count, stock_status, is_purchasable, purchase_status = _stock(product)
    sku = str(product.get("sku") or "").strip()
    product_key = (
        f"woocommerce:{parent_id}:variation:{item_id}"
        if parent_id is not None
        else f"woocommerce:{item_id}"
    )

    raw_json: dict[str, Any] = {
        "woocommerce_id": item_id,
        "parent_id": parent_id,
        "slug": str(product.get("slug") or "").strip(),
        "type": str(product.get("type") or "").strip(),
        "sku": sku,
        "permalink": permalink,
        "on_sale": _boolean(product, "on_sale"),
        "is_purchasable": is_purchasable,
        "is_in_stock": _boolean(product, "is_in_stock"),
        "is_on_backorder": _boolean(product, "is_on_backorder"),
        "low_stock_remaining": product.get("low_stock_remaining"),
        "prices": {
            "currency": prices["currency"],
            "minor_unit": prices["minor_unit"],
            "current_price": prices["current_price"],
            "regular_price": prices["regular_price"],
            "sale_price": prices["sale_price"],
            "price_range": prices["price_range"],
        },
        "categories": categories,
        "images": images,
    }
    if variant_attributes is not None:
        raw_json["variation_attributes"] = variant_attributes

    raw = {
        "token": token,
        "shop_name": shop_name,
        "shop_url": origin,
        "shop_status": "success",
        "source_platform": "woocommerce",
        "source_kind": "public_api",
        "product_key": product_key,
        "variant_key": str(item_id) if parent_id is not None else "",
        "sku": sku,
        "product_name": product_name,
        "category_name": category_name,
        "product_url": permalink,
        "listed_price": prices["current_price"],
        "current_price": prices["current_price"],
        "regular_price": prices["regular_price"],
        "sale_price": prices["sale_price"],
        "currency": prices["currency"],
        "stock_count": stock_count,
        "product_status": stock_status,
        "is_purchasable": is_purchasable,
        "purchase_status": purchase_status,
        "auto_delivery": None,
        "raw_json": raw_json,
    }
    return validate_record(raw)


def _variant_specifications(
    product: dict[str, Any],
) -> dict[int, tuple[str, list[dict[str, str]]]] | None:
    values = product.get("variations")
    if not isinstance(values, list) or not values:
        return None
    specifications: dict[int, tuple[str, list[dict[str, str]]]] = {}
    labels: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            return None
        variation_id = value.get("id")
        if isinstance(variation_id, bool) or not isinstance(variation_id, int) or variation_id <= 0:
            return None
        attributes = value.get("attributes")
        if not isinstance(attributes, list) or not attributes:
            return None
        normalized: list[dict[str, str]] = []
        attribute_names: set[str] = set()
        for attribute in attributes:
            if not isinstance(attribute, dict):
                return None
            attribute_name = str(attribute.get("name") or "").strip()
            attribute_value = str(attribute.get("value") or "").strip()
            if not attribute_name or not attribute_value or attribute_name in attribute_names:
                return None
            attribute_names.add(attribute_name)
            normalized.append({"name": attribute_name, "value": attribute_value})
        label = " / ".join(f"{item['name']}: {item['value']}" for item in normalized)
        if variation_id in specifications or label in labels:
            return None
        labels.add(label)
        specifications[variation_id] = (label, normalized)
    return specifications


def _expanded_variants(
    *,
    origin: str,
    token: str,
    shop_name: str,
    parent: dict[str, Any],
    variations: dict[int, dict[str, Any]],
) -> list[dict[str, Any]] | None:
    specifications = _variant_specifications(parent)
    if specifications is None:
        return None
    parent_id = _product_id(parent)
    records: list[dict[str, Any]] = []
    for variation_id, (label, attributes) in specifications.items():
        variation = variations.get(variation_id)
        if variation is None:
            return None
        if variation.get("parent") != parent_id or str(variation.get("type") or "") != "variation":
            return None
        try:
            records.append(
                _record(
                    origin=origin,
                    token=token,
                    shop_name=shop_name,
                    product=variation,
                    category_product=parent,
                    parent_id=parent_id,
                    variant_label=label,
                    variant_attributes=attributes,
                    require_complete_price=True,
                )
            )
        except (TypeError, ValueError):
            return None
    return records


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    parsed = _validate_store_url(str(source))
    origin = _origin(parsed)
    client = PinnedHTTPSClient(
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_task_bytes=MAX_TOTAL_BYTES,
        max_task_seconds=MAX_TASK_SECONDS,
        request_timeout=REQUEST_TIMEOUT,
        user_agent="AI-Price-Radar-Importer/3.6",
    )
    products = _fetch_collection(origin, client=client, capacity=MAX_PRODUCTS)
    needs_variations = any(
        str(product.get("type") or "") == "variable" and bool(product.get("variations"))
        for product in products
    )
    variation_items = (
        _fetch_collection(
            origin,
            client=client,
            product_type="variation",
            capacity=MAX_PRODUCTS - len(products),
        )
        if needs_variations
        else []
    )
    variations = {_product_id(item): item for item in variation_items}

    token = _shop_token(origin)
    shop_name = parsed.hostname or "WooCommerce"
    records: list[dict[str, Any]] = []
    for product in products:
        if str(product.get("type") or "") == "variable" and product.get("variations"):
            expanded = _expanded_variants(
                origin=origin,
                token=token,
                shop_name=shop_name,
                parent=product,
                variations=variations,
            )
            if expanded is not None:
                records.extend(expanded)
                continue
        records.append(
            _record(
                origin=origin,
                token=token,
                shop_name=shop_name,
                product=product,
            )
        )
    return records
