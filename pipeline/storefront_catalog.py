"""Normalize the public /api/products storefront catalog into a merchant feed."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import urlencode, urlsplit

from currencies import normalize_currency


class StaleStorefrontCatalog(ValueError):
    """The storefront cannot currently supply fresh public prices."""


def is_storefront_catalog(document: object) -> bool:
    return isinstance(document, dict) and {
        "products", "suppliers", "quoteState", "updatedAt", "validUntil",
    }.issubset(document)


def storefront_name(page: bytes, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page.decode("utf-8", errors="replace"), re.I | re.S)
    return unescape(match[1]).split("—", 1)[0].strip()[:200] if match else fallback


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("storefront catalog timestamp must be an ISO datetime")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("storefront catalog timestamp must include a timezone")
    return result


def normalize_storefront_catalog(document: dict, source_url: str, *, shop_name: str = "", now: datetime | None = None) -> dict:
    parsed = urlsplit(source_url)
    if parsed.scheme != "https" or parsed.path != "/api/products" or parsed.query or parsed.fragment:
        raise ValueError("storefront catalog must use the public /api/products URL")
    if not is_storefront_catalog(document) or not isinstance(document["products"], list) or not isinstance(document["suppliers"], list):
        raise ValueError("invalid storefront product catalog")
    now = now or datetime.now(timezone.utc)
    if document["quoteState"] != "fresh" or _timestamp(document["validUntil"]) <= now:
        raise StaleStorefrontCatalog("storefront prices are not fresh")
    _timestamp(document["updatedAt"])
    origin = f"https://{parsed.netloc}"
    suppliers = {}
    for supplier in document["suppliers"]:
        if not isinstance(supplier, dict) or not isinstance(supplier.get("id"), str) or not supplier["id"] or supplier["id"] in suppliers:
            raise ValueError("invalid or duplicate storefront supplier")
        suppliers[supplier["id"]] = supplier
    items, seen = [], set()
    stale_count = 0
    for product in document["products"]:
        if not isinstance(product, dict) or not isinstance(product.get("id"), str) or not product["id"] or not isinstance(product.get("name"), str) or not product["name"].strip():
            raise ValueError("storefront product requires an ID and name")
        if product["id"] in seen:
            raise ValueError("duplicate storefront product ID")
        seen.add(product["id"])
        if product.get("visible") is False or product.get("saleEnabled") is not True or product.get("checkoutSupported") is not True:
            continue
        supplier = suppliers.get(product.get("supplierId"))
        if supplier is None:
            raise ValueError("storefront product has no supplier freshness data")
        if supplier.get("quoteState") != "fresh" or supplier.get("status") != 200 or _timestamp(supplier.get("validUntil")) <= now or product.get("quoteState", "fresh") != "fresh":
            stale_count += 1
            continue
        _timestamp(supplier.get("updatedAt"))
        rmb_price = product.get("rmbPrice")
        price = rmb_price if rmb_price is not None else product.get("price")
        try:
            amount = Decimal(str(price))
        except InvalidOperation as exc:
            raise ValueError("invalid storefront price") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("invalid storefront price")
        stock = product.get("stock")
        if stock is not None and (type(stock) is not int or stock < 0):
            raise ValueError("invalid storefront stock")
        status = "out_of_stock" if stock == 0 else "in_stock"
        if stock is None and product.get("productType") not in {"slot", "upgrade_account"}:
            status = "unknown"
        items.append({
            **product,
            "url": f"{origin}/product?{urlencode({'id': product['id']})}",
            "upstream_price": product.get("price"),
            "upstream_currency": product.get("currency"),
            "price": str(amount),
            "currency": "CNY" if rmb_price is not None else normalize_currency(product.get("currency"), default=""),
            "stock_status": status,
            "observed_at": supplier["updatedAt"],
        })
    if stale_count and not items:
        raise StaleStorefrontCatalog("all available storefront prices are stale")
    return {
        "shop": {"name": shop_name or parsed.hostname, "url": origin},
        "updated_at": document["updatedAt"],
        "items": items,
    }
