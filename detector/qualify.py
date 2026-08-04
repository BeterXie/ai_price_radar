from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Iterable

from currencies import normalize_currency
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from probe import probe_source
from sitemap import product_page_urls, sitemap_locations

try:
    from classifier import classify_product
except ImportError:  # pragma: no cover - tests and the container provide classifier.py
    from services.classifier import classify_product  # type: ignore


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TASK_BYTES = 8 * 1024 * 1024
MAX_TASK_SECONDS = 45.0
REQUEST_TIMEOUT = 15.0
MAX_SAMPLE_PRODUCTS = 5
MAX_DUJIAO_PAGES = 3
MAX_WOO_PAGES = 3
MAX_SCHEMA_PAGES = 3
MAX_JSONLD_SCRIPTS = 50
MAX_JSONLD_NODES = 500
MONEY_PATTERN = re.compile(r"[0-9]+")
WOO_PAGE_SIZE = 50
WOO_MAX_PRODUCTS = 2_000
WOO_MAX_PAGES = 100


@dataclass(frozen=True, slots=True)
class QualificationResult:
    status: str
    detected_platform: str
    detected_source_key: str
    detected_source_url: str
    total_product_count: int
    ai_product_count: int
    sample_products: list[dict[str, str]]
    fingerprints: list[str]
    confidence_score: int
    failure_reason: str = ""


def _normalized_failure(value: str) -> str:
    return " ".join((value or "source validation failed").split())[:500]


def _json(response: PinnedResponse) -> Any:
    if response.status != 200:
        raise ValueError(f"source returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "").casefold()
    if content_type and "json" not in content_type:
        raise ValueError("source did not return JSON")
    return json.loads(response.body.decode("utf-8"))


def _localized(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for key in ("zh-CN", "zh-TW", "en-US", "en", *sorted(str(item) for item in value)):
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def _origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    rendered_host = f"[{host}]" if ":" in host else host
    return urllib.parse.urlunsplit(("https", rendered_host, "", "", ""))


def _same_origin_url(value: Any, origin: str, client: PinnedHTTPSClient) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith("#"):
        return None
    try:
        normalized = client.normalize_url(raw)
    except ValueError:
        return None
    if _origin(normalized) != origin:
        return None
    return normalized


def _append_sample(samples: list[dict[str, str]], name: str, url: str, slug: str = "") -> None:
    if len(samples) >= MAX_SAMPLE_PRODUCTS:
        return
    name = " ".join(name.split())[:200]
    if not name or len(url) > 2000:
        return
    item: dict[str, str] = {"name": name, "url": url}
    if slug:
        item["product_slug"] = slug[:200]
    samples.append(item)


def _classify(name: str, category: str = "") -> str | None:
    return classify_product(name, category).slug


def _dujiao_qualify(origin: str, client: PinnedHTTPSClient) -> QualificationResult:
    samples: list[dict[str, str]] = []
    total = 0
    ai_count = 0
    for page in range(1, MAX_DUJIAO_PAGES + 1):
        response = client.get(
            f"{origin}/api/v1/public/products?page={page}&page_size=100",
            accept="application/json",
        )
        document = _json(response)
        if not isinstance(document, dict) or document.get("status_code") != 0 or not isinstance(document.get("data"), list):
            raise ValueError("product API response is not Dujiao-Next public data")
        pagination = document.get("pagination")
        if not isinstance(pagination, dict):
            raise ValueError("product API response missing pagination")
        try:
            total_page = int(pagination.get("total_page"))
            total = int(pagination.get("total")) if pagination.get("total") is not None else total
        except (TypeError, ValueError) as exc:
            raise ValueError("product API pagination is invalid") from exc
        items = document["data"]
        for product in items:
            if not isinstance(product, dict):
                continue
            name = _localized(product.get("title"))
            slug = str(product.get("slug") or "").strip()
            if not name or not slug:
                continue
            if _classify(name):
                ai_count += 1
                _append_sample(
                    samples,
                    name,
                    f"{origin}/products/{urllib.parse.quote(slug, safe='')}",
                    slug,
                )
        if not items or page >= total_page:
            break
    return QualificationResult(
        status="detected",
        detected_platform="dujiao_next",
        detected_source_key=origin,
        detected_source_url=origin,
        total_product_count=max(total, len(samples)),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=["dujiao-next-public-api"],
        confidence_score=90,
    )


def _woocommerce_qualify(origin: str, client: PinnedHTTPSClient) -> QualificationResult:
    samples: list[dict[str, str]] = []
    ai_count = 0
    seen_ids: set[int] = set()
    expected_total: int | None = None
    expected_pages: int | None = None
    fully_validated = False
    page = 1
    while True:
        response = client.get(
            f"{origin}/wp-json/wc/store/v1/products?page={page}&per_page={WOO_PAGE_SIZE}",
            accept="application/json",
        )
        items = _json(response)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError("WooCommerce Store API product response must be an array of objects")
        headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
        total = _header_integer(headers, "x-wp-total")
        total_pages = _header_integer(headers, "x-wp-totalpages")
        calculated_pages = (total + WOO_PAGE_SIZE - 1) // WOO_PAGE_SIZE
        if total_pages != calculated_pages or total_pages > WOO_MAX_PAGES:
            raise ValueError("WooCommerce Store API pagination is invalid or exceeds the page limit")
        if total > WOO_MAX_PRODUCTS:
            raise ValueError("WooCommerce source exceeds the 2000 product limit")
        if expected_total is None:
            expected_total = total
            expected_pages = total_pages
        elif total != expected_total or total_pages != expected_pages:
            raise ValueError("WooCommerce Store API pagination changed during collection")
        expected_count = max(0, min(WOO_PAGE_SIZE, total - (page - 1) * WOO_PAGE_SIZE))
        if len(items) != expected_count:
            raise ValueError("WooCommerce Store API returned incomplete pagination")
        for item in items:
            item_id = item.get("id")
            if isinstance(item_id, bool) or not isinstance(item_id, int) or item_id <= 0:
                raise ValueError("WooCommerce Store API product id is invalid")
            if item_id in seen_ids:
                raise ValueError("WooCommerce Store API returned a duplicate product id")
            seen_ids.add(item_id)
            _validate_woo_prices(item.get("prices"))
        for item in items:
            if item.get("is_purchasable") is not True:
                continue
            prices = item.get("prices")
            if not isinstance(prices, dict) or prices.get("price") is None:
                continue
            name = str(item.get("name") or "").strip()
            permalink = _same_origin_url(item.get("permalink"), origin, client)
            if not name or not permalink:
                continue
            if _classify(name):
                ai_count += 1
                _append_sample(
                    samples,
                    name,
                    permalink,
                    str(item.get("slug") or ""),
                )
        if page >= total_pages:
            fully_validated = True
            break
        if len(items) < WOO_PAGE_SIZE:
            break
        page += 1
        if page > MAX_WOO_PAGES:
            break
    fingerprints = ["woocommerce-store-api"]
    if not fully_validated:
        fingerprints.append("woocommerce-partial-scan")
    return QualificationResult(
        status="detected",
        detected_platform="woocommerce",
        detected_source_key=origin,
        detected_source_url=origin,
        total_product_count=expected_total or len(samples),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=fingerprints,
        confidence_score=88 if fully_validated else 49,
    )


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._chunks: list[str] = []
        self.documents: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.casefold(): str(value or "").casefold() for name, value in attrs}
        if tag.casefold() == "script" and attributes.get("type", "").split(";", 1)[0].strip() == "application/ld+json":
            self._capturing = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "script" or not self._capturing:
            return
        self._capturing = False
        try:
            self.documents.append(json.loads("".join(self._chunks)))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        self._chunks = []


def _jsonld_product_nodes(body: bytes) -> list[dict[str, Any]]:
    parser = _JsonLdParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    nodes: list[dict[str, Any]] = []
    visited = 0

    def walk(value: Any) -> Iterable[dict[str, Any]]:
        nonlocal visited
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            visited += 1
            if visited > MAX_JSONLD_NODES:
                raise ValueError("page exceeds JSON-LD node limit")
            raw_types = value.get("@type")
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            if any(str(item).rsplit("/", 1)[-1].rstrip("#").casefold() == "product" for item in types):
                yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from walk(child)

    for document in parser.documents:
        try:
            nodes.extend(walk(document))
        except ValueError:
            raise
        if len(nodes) > MAX_JSONLD_NODES:
            raise ValueError("page exceeds JSON-LD product limit")
    return nodes


def _minor_amount_text(value: Any, field: str) -> str | None:
    """Mirror pipeline.connectors.woocommerce_store._minor_amount validation rules."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"WooCommerce {field} must use integer minor units")
    text = str(value)
    if text != text.strip() or MONEY_PATTERN.fullmatch(text) is None:
        raise ValueError(f"WooCommerce {field} must use integer minor units")
    return text


def _validate_woo_prices(prices: Any) -> None:
    """Strictly mirror the WooCommerce Connector price contract; raises on invalid data."""
    if not isinstance(prices, dict):
        raise ValueError("WooCommerce Store API product prices are invalid")
    minor_unit = prices.get("currency_minor_unit")
    if isinstance(minor_unit, bool) or not isinstance(minor_unit, int) or not 0 <= minor_unit <= 12:
        raise ValueError("WooCommerce currency_minor_unit is invalid")
    normalize_currency(prices.get("currency_code"))
    _minor_amount_text(prices.get("price"), "current price")
    _minor_amount_text(prices.get("regular_price"), "regular price")
    _minor_amount_text(prices.get("sale_price"), "sale price")
    price_range = prices.get("price_range")
    if price_range is not None:
        if not isinstance(price_range, dict):
            raise ValueError("WooCommerce product price range is invalid")
        _minor_amount_text(price_range.get("min_amount"), "minimum price")
        _minor_amount_text(price_range.get("max_amount"), "maximum price")


def _header_integer(headers: dict[str, str], field: str) -> int:
    value = headers.get(field)
    if value is None or not str(value).strip().isdigit():
        raise ValueError(f"WooCommerce Store API response missing or invalid {field} header")
    return int(str(value).strip())


def _valid_amount(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def _price_of_product(product: dict[str, Any]) -> tuple[str | None, str | None]:
    offers = product.get("offers")
    values = offers if isinstance(offers, list) else [offers]
    prices: list[Decimal] = []
    currencies: set[str] = set()
    for offer in values:
        if not isinstance(offer, dict):
            continue
        amount = offer.get("lowPrice") or offer.get("price")
        currency = offer.get("priceCurrency") or product.get("priceCurrency")
        if currency in (None, ""):
            continue
        try:
            normalized_currency = normalize_currency(currency, default="")
        except ValueError:
            continue
        parsed_amount = _valid_amount(amount)
        if parsed_amount is None:
            continue
        prices.append(parsed_amount)
        currencies.add(normalized_currency)
    if not prices or len(currencies) != 1:
        return None, None
    return format(min(prices), "f"), currencies.pop()


def _schema_scan_pages(
    page_urls: list[str],
    origin: str,
    client: PinnedHTTPSClient,
) -> tuple[int, int, list[dict[str, str]]]:
    samples: list[dict[str, str]] = []
    ai_count = 0
    total = 0
    for page_url in page_urls:
        try:
            page = client.get(page_url, accept="text/html,application/xhtml+xml")
        except (OSError, TimeoutError, ValueError):
            continue
        nodes = _jsonld_product_nodes(page.body)
        total += len(nodes)
        for product in nodes:
            name = str(product.get("name") or "").strip()
            if not name or not _classify(name):
                continue
            price, currency = _price_of_product(product)
            if price is None or currency is None:
                continue
            url = _same_origin_url(product.get("url") or product.get("@id") or page_url, origin, client)
            if url is None:
                continue
            ai_count += 1
            _append_sample(samples, name, url)
        if ai_count:
            break
    return total, ai_count, samples


def _schema_qualify(entry: str, client: PinnedHTTPSClient) -> QualificationResult:
    origin = _origin(entry)
    response = client.get(entry, accept="application/xml,text/xml,text/html;q=0.9,*/*;q=0.1")
    try:
        kind, _locations = sitemap_locations(response.body)
    except ValueError as exc:
        if b"<html" in response.body.lower():
            kind = ""
        else:
            return _schema_failure(entry, str(exc))
    is_root = urllib.parse.urlsplit(entry).path in ("", "/")
    sitemap_entry: str | None = None
    fingerprints: list[str] = []

    if kind in {"urlset", "sitemapindex"}:
        sitemap_entry = entry
        fingerprints.append("schema-org-sitemap")
    else:
        nodes = _jsonld_product_nodes(response.body)
        if nodes:
            fingerprints.append("schema-org-jsonld")
            total, ai_count, samples = _schema_scan_pages([entry], origin, client)
            return _schema_result(entry, total, ai_count, samples, fingerprints)
        if not is_root:
            return _schema_result(entry, 0, 0, [], [])
        try:
            sitemap_response = client.get(f"{origin}/sitemap.xml", accept="application/xml,text/xml")
            sitemap_kind, _ignored_locations = sitemap_locations(sitemap_response.body)
        except (OSError, TimeoutError, ValueError):
            sitemap_kind = ""
        if sitemap_kind in {"urlset", "sitemapindex"}:
            sitemap_entry = f"{origin}/sitemap.xml"
            fingerprints.append("schema-org-sitemap")
        else:
            return _schema_result(entry, 0, 0, [], [])

    if sitemap_entry is not None:
        try:
            preloaded = (
                sitemap_response
                if sitemap_entry != entry
                else response
            )
            page_urls = product_page_urls(sitemap_entry, origin, client, preloaded=preloaded)
        except ValueError as exc:
            return _schema_failure(entry, str(exc))
        total, ai_count, samples = _schema_scan_pages(page_urls, origin, client)
        return _schema_result(entry, total, ai_count, samples, fingerprints)
    return _schema_result(entry, 0, 0, [], fingerprints)


def _schema_result(
    entry: str,
    total: int,
    ai_count: int,
    samples: list[dict[str, str]],
    fingerprints: list[str],
) -> QualificationResult:
    return QualificationResult(
        status="detected",
        detected_platform="schema_org",
        detected_source_key=entry,
        detected_source_url=entry,
        total_product_count=total or len(samples),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=fingerprints,
        confidence_score=80,
    )


def _schema_failure(entry: str, reason: str) -> QualificationResult:
    return QualificationResult(
        status="validation_failed",
        detected_platform="schema_org",
        detected_source_key=entry,
        detected_source_url=entry,
        total_product_count=0,
        ai_product_count=0,
        sample_products=[],
        fingerprints=[],
        confidence_score=0,
        failure_reason=_normalized_failure(reason),
    )


def _merchant_qualify(entry: str, client: PinnedHTTPSClient) -> QualificationResult:
    document = _json(client.get(entry, accept="application/json"))
    items = document if isinstance(document, list) else document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise ValueError("merchant feed must contain an items list")
    samples: list[dict[str, str]] = []
    ai_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = _same_origin_url(item.get("url") or "", _origin(entry), client)
        if not name or not url or not _classify(name):
            continue
        ai_count += 1
        _append_sample(samples, name, url, str(item.get("id") or ""))
    return QualificationResult(
        status="detected",
        detected_platform="merchant_json",
        detected_source_key=entry,
        detected_source_url=entry,
        total_product_count=max(len(items), len(samples)),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=["merchant-json-feed"],
        confidence_score=75,
    )


def qualify_candidate(
    canonical_url: str,
    platform_hint: str,
    *,
    client: PinnedHTTPSClient | None = None,
) -> QualificationResult:
    client = client or PinnedHTTPSClient(
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_task_bytes=MAX_TASK_BYTES,
        max_task_seconds=MAX_TASK_SECONDS,
        request_timeout=REQUEST_TIMEOUT,
        user_agent="AI-Price-Radar-Detector/3.7",
    )
    try:
        probe = probe_source(canonical_url, client=client)
        platform = probe.detected_platform
        source_key = probe.source_key or canonical_url
        source_url = probe.source_url or canonical_url
        if platform in {"other", "unknown"}:
            if _looks_like_schema_candidate(canonical_url, platform_hint):
                try:
                    return _schema_qualify(canonical_url, client)
                except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    return _schema_failure(canonical_url, str(exc))
            return QualificationResult(
                status="no_match",
                detected_platform=platform,
                detected_source_key=source_key,
                detected_source_url=source_url,
                total_product_count=0,
                ai_product_count=0,
                sample_products=[],
                fingerprints=[],
                confidence_score=0,
                failure_reason="平台未能识别为支持的公开来源",
            )
        if platform == "ldxp":
            return QualificationResult(
                status="no_match",
                detected_platform="ldxp",
                detected_source_key=source_key,
                detected_source_url=source_url,
                total_product_count=0,
                ai_product_count=0,
                sample_products=[],
                fingerprints=[],
                confidence_score=0,
                failure_reason="LDXP 沿用现有收录流程",
            )
        if platform == "dujiao_next":
            return _dujiao_qualify(_origin(source_url), client)
        if platform == "woocommerce":
            return _woocommerce_qualify(_origin(source_url), client)
        if platform == "schema_org":
            return _schema_qualify(source_url, client)
        if platform == "merchant_json":
            return _merchant_qualify(source_url, client)
        return QualificationResult(
            status="no_match",
            detected_platform=platform,
            detected_source_key=source_key,
            detected_source_url=source_url,
            total_product_count=0,
            ai_product_count=0,
            sample_products=[],
            fingerprints=[],
            confidence_score=0,
            failure_reason="来源类型暂不支持自动准入",
        )
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return QualificationResult(
            status="validation_failed",
            detected_platform="unknown",
            detected_source_key="",
            detected_source_url="",
            total_product_count=0,
            ai_product_count=0,
            sample_products=[],
            fingerprints=[],
            confidence_score=0,
            failure_reason=_normalized_failure(type(exc).__name__ + ": " + str(exc)),
        )


def _looks_like_schema_candidate(value: str, platform_hint: str) -> bool:
    hint = str(platform_hint or "").strip().casefold().replace("-", "_")
    if hint == "schema_org":
        return True
    path = urllib.parse.urlsplit(str(value)).path.casefold()
    return path.endswith(".xml") or "sitemap" in path
