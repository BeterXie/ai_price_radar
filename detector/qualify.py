from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Iterable

from price_radar_http import PinnedHTTPSClient, PinnedResponse

from probe import probe_source

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
MAX_SCHEMA_LOCATIONS = 50
MAX_JSONLD_SCRIPTS = 50
MAX_JSONLD_NODES = 500


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
    total = 0
    ai_count = 0
    for page in range(1, MAX_WOO_PAGES + 1):
        response = client.get(
            f"{origin}/wp-json/wc/store/v1/products?page={page}&per_page=50",
            accept="application/json",
        )
        items = _json(response)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError("WooCommerce Store API product response must be an array of objects")
        if not total:
            try:
                total = int(response.headers.get("x-wp-total") or 0)
            except (TypeError, ValueError):
                total = 0
        for item in items:
            if item.get("is_purchasable") is not True:
                continue
            prices = item.get("prices")
            if not isinstance(prices, dict) or prices.get("price") is None or not prices.get("currency_code"):
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
        if len(items) < 50:
            break
    return QualificationResult(
        status="detected",
        detected_platform="woocommerce",
        detected_source_key=origin,
        detected_source_url=origin,
        total_product_count=total or len(samples),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=["woocommerce-store-api"],
        confidence_score=88,
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


def _sitemap_locations(body: bytes) -> tuple[str, list[str]]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return "", []
    kind = root.tag.rsplit("}", 1)[-1].casefold()
    if kind not in {"urlset", "sitemapindex"}:
        return "", []
    locations = [
        str(node.text or "").strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].casefold() == "loc" and str(node.text or "").strip()
    ]
    return kind, locations


def _price_of_product(product: dict[str, Any]) -> tuple[str | None, str | None]:
    offers = product.get("offers")
    values = offers if isinstance(offers, list) else [offers]
    prices: list[str] = []
    currencies: set[str] = set()
    for offer in values:
        if not isinstance(offer, dict):
            continue
        amount = offer.get("lowPrice") or offer.get("price")
        currency = offer.get("priceCurrency") or product.get("priceCurrency")
        if amount in (None, "") or currency in (None, ""):
            continue
        if isinstance(amount, bool) or not isinstance(amount, (str, int, float)):
            continue
        prices.append(str(amount))
        currencies.add(str(currency))
    if not prices or len(currencies) != 1:
        return None, None
    return min(prices, key=lambda value: float(value) if str(value).replace(".", "", 1).isdigit() else float("inf")), currencies.pop()


def _schema_qualify(entry: str, client: PinnedHTTPSClient) -> QualificationResult:
    origin = _origin(entry)
    samples: list[dict[str, str]] = []
    ai_count = 0
    total = 0
    fingerprints: list[str] = []
    response = client.get(entry, accept="application/xml,text/xml,text/html;q=0.9,*/*;q=0.1")
    kind, locations = _sitemap_locations(response.body)
    if kind in {"urlset", "sitemapindex"}:
        fingerprints.append("schema-org-sitemap")
        page_urls = [_same_origin_url(value, origin, client) for value in locations[:MAX_SCHEMA_LOCATIONS]]
        page_urls = [value for value in page_urls if value]
        for page_url in page_urls[:MAX_SCHEMA_PAGES]:
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
            if nodes:
                break
        return QualificationResult(
            status="detected",
            detected_platform="schema_org",
            detected_source_key=entry,
            detected_source_url=entry,
            total_product_count=max(total, len(samples)),
            ai_product_count=ai_count,
            sample_products=samples,
            fingerprints=fingerprints,
            confidence_score=80,
        )

    nodes = _jsonld_product_nodes(response.body)
    if not nodes and urllib.parse.urlsplit(entry).path in ("", "/"):
        try:
            sitemap = client.get(f"{origin}/sitemap.xml", accept="application/xml,text/xml")
            kind, locations = _sitemap_locations(sitemap.body)
        except (OSError, TimeoutError, ValueError):
            kind = ""
        if kind in {"urlset", "sitemapindex"}:
            return _schema_qualify(f"{origin}/sitemap.xml", client)
    for product in nodes:
        total += 1
        name = str(product.get("name") or "").strip()
        if not name or not _classify(name):
            continue
        price, currency = _price_of_product(product)
        if price is None or currency is None:
            continue
        url = _same_origin_url(product.get("url") or product.get("@id") or entry, origin, client)
        if url is None:
            continue
        ai_count += 1
        _append_sample(samples, name, url)
    return QualificationResult(
        status="detected",
        detected_platform="schema_org",
        detected_source_key=entry,
        detected_source_url=entry,
        total_product_count=max(total, len(samples)),
        ai_product_count=ai_count,
        sample_products=samples,
        fingerprints=["schema-org-jsonld"] if nodes else [],
        confidence_score=80,
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
