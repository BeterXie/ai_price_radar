from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from price_radar_http import PinnedHTTPSClient, PinnedResponse

from currencies import normalize_currency

from .base import validate_record


name = "schema-org"

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_TOTAL_SECONDS = 120.0
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_SITEMAP_DEPTH = 3
MAX_SITEMAPS = 32
MAX_PRODUCT_URLS = 2_000
MAX_JSONLD_SCRIPTS = 100
MAX_JSONLD_NODES = 2_000

_JSONLD_MEDIA_TYPE = "application/ld+json"
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class _Price:
    amount: Decimal
    rendered: str
    currency: str
    availability: str
    field: str


class _JSONLDScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.documents: list[str] = []
        self._parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script" or self._parts is not None:
            return
        attributes = {key.casefold(): value or "" for key, value in attrs}
        media_type = attributes.get("type", "").split(";", 1)[0].strip().casefold()
        if media_type == _JSONLD_MEDIA_TYPE:
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._parts is not None:
            self.documents.append("".join(self._parts))
            self._parts = None


class _FetchBudget:
    def __init__(self, client: PinnedHTTPSClient) -> None:
        self.client = client
        self.started = time.monotonic()
        self.total_bytes = 0
        self.requests = 0

    def get(self, url: str, *, accept: str) -> PinnedResponse:
        self._check_time()
        self.requests += 1
        if self.requests > MAX_SITEMAPS + MAX_PRODUCT_URLS:
            raise ValueError("Schema.org source exceeds request limit")
        response = self.client.get(url, accept=accept)
        self._check_time()
        if response.status != 200:
            raise ValueError(f"Schema.org source returned HTTP {response.status}")
        headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
        encoding = headers.get("content-encoding", "").strip().casefold()
        if encoding and encoding != "identity":
            raise ValueError("Schema.org source must not use compressed response encoding")
        body = response.body
        if not isinstance(body, bytes):
            raise ValueError("Schema.org source returned a non-bytes response")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Schema.org source response exceeds size limit")
        try:
            declared_length = int(headers.get("content-length", "0"))
        except ValueError as exc:
            raise ValueError("Schema.org source returned invalid Content-Length") from exc
        if declared_length < 0 or declared_length > MAX_RESPONSE_BYTES:
            raise ValueError("Schema.org source response exceeds size limit")
        self.total_bytes += len(body)
        if self.total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Schema.org source exceeds total byte limit")
        return response

    def _check_time(self) -> None:
        if time.monotonic() - self.started > MAX_TOTAL_SECONDS:
            raise TimeoutError("Schema.org source exceeded total time limit")


def _normalized_url(value: object, *, base_url: str | None = None) -> str:
    raw = str(value or "")
    if not raw or raw != raw.strip() or _CONTROL_CHARACTERS.search(raw) or "#" in raw:
        raise ValueError("URL must not be empty or contain whitespace, control characters, or a fragment")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme and parsed.scheme.casefold() != "https":
        raise ValueError("URL must use HTTPS")
    if not parsed.scheme and base_url is None:
        raise ValueError("URL must be absolute")
    absolute = urllib.parse.urljoin(base_url, raw) if base_url is not None else raw
    return PinnedHTTPSClient.normalize_url(absolute)


def _origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    rendered_host = f"[{host}]" if ":" in host else host
    return urllib.parse.urlunsplit(("https", rendered_host, "", "", ""))


def _same_origin(url: str, origin: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    expected = urllib.parse.urlsplit(origin)
    return (
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() == (expected.hostname or "").casefold()
        and (parsed.port or 443) == 443
    )


def _safe_same_origin_url(value: object, *, base_url: str, origin: str) -> str | None:
    if isinstance(value, dict):
        value = value.get("@id") or value.get("url")
    if isinstance(value, list):
        for item in value:
            candidate = _safe_same_origin_url(item, base_url=base_url, origin=origin)
            if candidate:
                return candidate
        return None
    try:
        candidate = _normalized_url(value, base_url=base_url)
    except (TypeError, ValueError):
        return None
    return candidate if _same_origin(candidate, origin) else None


def _entry(source: str | Path) -> tuple[str, str, str]:
    normalized = _normalized_url(str(source))
    origin = _origin(normalized)
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.path == "/" and not parsed.query:
        sitemap_url = f"{origin}/sitemap.xml"
    else:
        sitemap_url = None
    return normalized, origin, sitemap_url


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _sitemap_locations(body: bytes) -> tuple[str, list[str]]:
    lowered = body.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("Schema.org sitemap must not contain DTD or entity declarations")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("Schema.org sitemap is invalid XML") from exc
    kind = _local_name(root.tag)
    if kind not in {"sitemapindex", "urlset"}:
        raise ValueError("Schema.org source is not a sitemap or sitemap index")
    locations = [
        str(element.text or "").strip()
        for element in root.iter()
        if _local_name(element.tag) == "loc" and str(element.text or "").strip()
    ]
    return kind, locations


def _discover_product_pages(
    sitemap_url: str,
    origin: str,
    budget: _FetchBudget,
    *,
    preloaded: PinnedResponse | None = None,
) -> list[str]:
    queue: list[tuple[str, int]] = [(sitemap_url, 0)]
    seen_sitemaps = {sitemap_url}
    product_urls: list[str] = []
    seen_products: set[str] = set()

    while queue:
        current_url, depth = queue.pop(0)
        if preloaded is not None and current_url == sitemap_url:
            response = preloaded
            preloaded = None
        else:
            response = budget.get(
                current_url,
                accept="application/xml,text/xml;q=0.9,*/*;q=0.1",
            )
        kind, locations = _sitemap_locations(response.body)
        if kind == "sitemapindex":
            if depth >= MAX_SITEMAP_DEPTH and locations:
                raise ValueError("Schema.org sitemap index exceeds recursion depth limit")
            for raw_location in locations:
                candidate = _safe_same_origin_url(
                    raw_location,
                    base_url=current_url,
                    origin=origin,
                )
                if candidate is None or candidate in seen_sitemaps:
                    continue
                seen_sitemaps.add(candidate)
                if len(seen_sitemaps) > MAX_SITEMAPS:
                    raise ValueError("Schema.org source exceeds sitemap count limit")
                queue.append((candidate, depth + 1))
            continue

        for raw_location in locations:
            candidate = _safe_same_origin_url(
                raw_location,
                base_url=current_url,
                origin=origin,
            )
            if candidate is None or candidate in seen_products:
                continue
            seen_products.add(candidate)
            if len(seen_products) > MAX_PRODUCT_URLS:
                raise ValueError("Schema.org source exceeds product URL limit")
            product_urls.append(candidate)
    return product_urls


def _looks_like_sitemap_url(url: str) -> bool:
    path = urllib.parse.urlsplit(url).path.casefold()
    return path.endswith(".xml") or "sitemap" in path


def _entry_pages(
    entry_url: str,
    origin: str,
    budget: _FetchBudget,
) -> tuple[list[str], dict[str, PinnedResponse]]:
    response = budget.get(
        entry_url,
        accept="application/xml,text/xml,text/html;q=0.9,*/*;q=0.1",
    )
    try:
        _sitemap_locations(response.body)
    except ValueError as exc:
        nodes = _jsonld_nodes(response.body)
        if any(_has_type(node, "Product") for node in nodes):
            return [entry_url], {entry_url: response}
        if _looks_like_sitemap_url(entry_url):
            raise
        raise ValueError(
            "Schema.org source is not a sitemap or a page with Product JSON-LD"
        ) from None
    return _discover_product_pages(
        entry_url,
        origin,
        budget,
        preloaded=response,
    ), {}


def _schema_type(value: object) -> str:
    text = str(value or "").strip().rstrip("/")
    return re.split(r"[/#: ]", text)[-1].casefold()


def _has_type(node: dict[str, Any], expected: str) -> bool:
    values = node.get("@type")
    if not isinstance(values, list):
        values = [values]
    return any(_schema_type(value) == expected.casefold() for value in values)


def _walk_jsonld(value: Any) -> Iterator[dict[str, Any]]:
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            visited += 1
            if visited > MAX_JSONLD_NODES:
                raise ValueError("Schema.org page exceeds JSON-LD node limit")
            yield current
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))


def _jsonld_nodes(body: bytes) -> list[dict[str, Any]]:
    parser = _JSONLDScriptParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
        parser.close()
    except Exception:
        return []
    if len(parser.documents) > MAX_JSONLD_SCRIPTS:
        raise ValueError("Schema.org page exceeds JSON-LD script limit")
    nodes: list[dict[str, Any]] = []
    for script in parser.documents:
        try:
            document = json.loads(script)
            nodes.extend(_walk_jsonld(document))
        except (json.JSONDecodeError, RecursionError, TypeError, ValueError):
            continue
        if len(nodes) > MAX_JSONLD_NODES:
            raise ValueError("Schema.org page exceeds JSON-LD node limit")
    return nodes


def _reference_map(nodes: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    for node in nodes:
        identifier = node.get("@id")
        if isinstance(identifier, str) and identifier.strip():
            existing = references.get(identifier)
            if existing is None or len(node) > len(existing):
                references[identifier] = node
    return references


def _resolved_values(value: object, references: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    resolved: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, str):
            item = references.get(item)
        elif isinstance(item, dict) and set(item) == {"@id"}:
            item = references.get(str(item.get("@id") or ""), item)
        if isinstance(item, dict):
            resolved.append(item)
    return resolved


def _amount(value: object) -> tuple[Decimal, str] | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount, format(amount, "f")


def _currency(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        return normalize_currency(value, default="")
    except ValueError:
        return None


def _availability(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("@id") or value.get("name")
    if not isinstance(value, str):
        return ""
    token = _schema_type(value)
    aliases = {
        "instock": "in_stock",
        "limitedavailability": "limited_availability",
        "onlineonly": "online_only",
        "outofstock": "out_of_stock",
        "soldout": "out_of_stock",
        "preorder": "pre_order",
        "presale": "pre_sale",
        "backorder": "back_order",
        "discontinued": "discontinued",
    }
    return aliases.get(token, token)


def _price_from_offer(
    offer: dict[str, Any],
    *,
    product: dict[str, Any],
) -> list[_Price]:
    aggregate = _has_type(offer, "AggregateOffer") or "lowPrice" in offer
    field = "lowPrice" if aggregate else "price"
    raw_amount = offer.get(field)
    amount = _amount(raw_amount)
    currency_value = offer.get("priceCurrency") or product.get("priceCurrency")

    if amount is None and not aggregate:
        specifications = offer.get("priceSpecification")
        specifications = specifications if isinstance(specifications, list) else [specifications]
        prices: list[_Price] = []
        for specification in specifications:
            if not isinstance(specification, dict):
                continue
            parsed_amount = _amount(specification.get("price"))
            parsed_currency = _currency(
                specification.get("priceCurrency") or currency_value
            )
            if parsed_amount is not None and parsed_currency is not None:
                prices.append(
                    _Price(
                        parsed_amount[0],
                        parsed_amount[1],
                        parsed_currency,
                        _availability(offer.get("availability") or product.get("availability")),
                        "priceSpecification.price",
                    )
                )
        return prices

    parsed_currency = _currency(currency_value)
    if amount is None or parsed_currency is None:
        return []
    return [
        _Price(
            amount[0],
            amount[1],
            parsed_currency,
            _availability(offer.get("availability") or product.get("availability")),
            field,
        )
    ]


def _select_price(
    product: dict[str, Any],
    references: dict[str, dict[str, Any]],
) -> _Price | None:
    offers = _resolved_values(product.get("offers"), references)
    candidates = [
        price
        for offer in offers
        for price in _price_from_offer(offer, product=product)
    ]
    if not candidates or len({candidate.currency for candidate in candidates}) != 1:
        return None
    return min(candidates, key=lambda candidate: candidate.amount)


def _text(value: object) -> str:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _category(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("@id")
    if isinstance(value, list):
        return " / ".join(filter(None, (_category(item) for item in value)))
    return _text(value)


def _product_url(product: dict[str, Any], *, page_url: str, origin: str) -> str:
    for value in (
        product.get("url"),
        product.get("mainEntityOfPage"),
        product.get("@id"),
    ):
        candidate = _safe_same_origin_url(value, base_url=page_url, origin=origin)
        if candidate:
            return candidate
    return page_url


def _product_key(product: dict[str, Any], product_url: str) -> tuple[str, str]:
    for field in ("sku", "productID", "mpn", "gtin", "gtin8", "gtin12", "gtin13", "gtin14"):
        value = _text(product.get(field))
        if value:
            return f"{field}:{value}"[:300], value if field == "sku" else ""
    return f"url:{product_url}"[:300], ""


def _record(
    product: dict[str, Any],
    *,
    page_url: str,
    origin: str,
    token: str,
    references: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    product_name = _text(product.get("name"))
    price = _select_price(product, references)
    if not product_name or price is None:
        return None
    product_url = _product_url(product, page_url=page_url, origin=origin)
    product_key, sku = _product_key(product, product_url)
    stock_count = 0 if price.availability in {"out_of_stock", "discontinued"} else None
    raw_json = dict(product)
    raw_json["schema_org_page_url"] = page_url
    raw_json["schema_org_price_field"] = price.field
    raw = {
        "token": token,
        "shop_name": urllib.parse.urlsplit(origin).hostname or "Schema.org shop",
        "shop_url": origin,
        "shop_status": "success",
        "source_platform": "schema_org",
        "source_kind": "sitemap_jsonld",
        "product_key": product_key,
        "variant_key": sku,
        "product_name": product_name,
        "category_name": _category(product.get("category")),
        "product_url": product_url,
        "listed_price": price.rendered,
        "currency": price.currency,
        "stock_count": stock_count,
        "product_status": price.availability,
        "auto_delivery": None,
        "raw_json": raw_json,
    }
    return validate_record(raw)


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    _normalized_entry, origin, sitemap_url = _entry(source)
    client = PinnedHTTPSClient(
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_task_bytes=MAX_TOTAL_BYTES,
        max_task_seconds=MAX_TOTAL_SECONDS,
        request_timeout=REQUEST_TIMEOUT_SECONDS,
        user_agent="AI-Price-Radar-Importer/3.6",
    )
    budget = _FetchBudget(client)
    preloaded_pages: dict[str, PinnedResponse] = {}
    if sitemap_url is None:
        pages, preloaded_pages = _entry_pages(_normalized_entry, origin, budget)
    else:
        pages = _discover_product_pages(sitemap_url, origin, budget)
    token = "schema-org-" + hashlib.sha256(origin.encode("utf-8")).hexdigest()[:20]
    seen_products: set[str] = set()

    for page_url in pages:
        response = preloaded_pages.get(page_url) or budget.get(
            page_url,
            accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        )
        nodes = _jsonld_nodes(response.body)
        references = _reference_map(nodes)
        for product in nodes:
            if not _has_type(product, "Product"):
                continue
            record = _record(
                product,
                page_url=page_url,
                origin=origin,
                token=token,
                references=references,
            )
            if record is None:
                continue
            identity = record["product_key"]
            if identity in seen_products:
                continue
            seen_products.add(identity)
            yield record
