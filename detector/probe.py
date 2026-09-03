from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from price_radar_http import PinnedHTTPSClient, PinnedResponse as ProbeResponse
from sitemap import product_page_urls, sitemap_locations


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TASK_BYTES = 2 * 1024 * 1024
MAX_TASK_SECONDS = 15.0
LDXP_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn", "wzyp.cn", "www.wzyp.cn"}
LDXP_PATH = re.compile(r"/shop/([A-Za-z0-9._~-]+)", re.IGNORECASE)
PLATFORM_16688_HOSTS = {"16688.com.cn", "www.16688.com.cn"}
PLATFORM_16688_PATH = re.compile(r"/shop/([A-Za-z0-9._~-]+)", re.IGNORECASE)
PLATFORM_16688_CODE = re.compile(r"[A-Za-z0-9._~-]{1,128}")


@dataclass(frozen=True, slots=True)
class ProbeResult:
    detected_platform: str
    source_url: str
    source_key: str
    shop_name: str = ""
    product_count: int = 0


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

def _json(response: ProbeResponse) -> Any:
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


def _schema_product_count(body: bytes) -> int:
    parser = _JsonLdParser()
    parser.feed(body.decode("utf-8", errors="replace"))

    def walk(value: Any):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            raw_types = value.get("@type")
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            if any(str(item).casefold() == "product" for item in types):
                yield value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    yield from walk(child)

    return sum(1 for document in parser.documents for _ in walk(document))


def _schema_from_sitemap(
    origin: str,
    client: PinnedHTTPSClient,
    *,
    entry_url: str | None = None,
    preloaded: ProbeResponse | None = None,
) -> tuple[str, int] | None:
    try:
        if entry_url is not None:
            response = preloaded or client.get(entry_url, accept="application/xml,text/xml")
            sitemap_locations(response.body)
        page_urls = product_page_urls(
            entry_url or f"{origin}/sitemap.xml",
            origin,
            client,
            preloaded=response if entry_url is not None else None,
        )
    except (OSError, TimeoutError, ValueError):
        return None
    for page_url in page_urls:
        try:
            response = client.get(page_url, accept="text/html,application/xhtml+xml")
        except (OSError, TimeoutError, ValueError):
            continue
        if response.status == 200 and (count := _schema_product_count(response.body)):
            return page_url, count
    return None


def _probe_16688(
    parsed: urllib.parse.SplitResult,
    requested_shop_no: str,
    client: PinnedHTTPSClient,
) -> ProbeResult:
    if not PLATFORM_16688_CODE.fullmatch(requested_shop_no):
        raise ValueError("16688 shop code is invalid")
    host = (parsed.hostname or "").casefold()
    origin = urllib.parse.urlunsplit(("https", host, "", "", ""))
    detail = _json(client.post_json(
        f"{origin}/shopApi/shop/detail",
        {"shop_no": requested_shop_no},
    ))
    if not isinstance(detail, dict) or detail.get("code") != 1 or not isinstance(detail.get("data"), dict):
        raise ValueError("source is not a valid 16688 shop")
    shop = detail["data"]
    shop_no = str(shop.get("shop_no") or requested_shop_no).strip()
    if not PLATFORM_16688_CODE.fullmatch(shop_no):
        raise ValueError("16688 shop detail returned an invalid shop number")
    listing = _json(client.post_json(
        f"{origin}/shopApi/goods/list",
        {"shop_no": shop_no, "sort": "default"},
    ))
    if not isinstance(listing, dict) or listing.get("code") != 1:
        raise ValueError("16688 goods API returned an error")
    data = listing.get("data")
    items = data.get("list") if isinstance(data, dict) else None
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("16688 goods API response is invalid")
    source_url = f"{origin}/shop/{urllib.parse.quote(shop_no, safe='._~-')}"
    shop_name = str(shop.get("name") or shop_no or host).strip()
    return ProbeResult("16688", source_url, source_url, shop_name, len(items))


def probe_source(value: object, *, client: PinnedHTTPSClient | None = None) -> ProbeResult:
    client = client or PinnedHTTPSClient(
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_task_bytes=MAX_TASK_BYTES,
        max_task_seconds=MAX_TASK_SECONDS,
        user_agent="AI-Price-Radar-Detector/1",
    )
    normalized = client.normalize_url(value)
    parsed = urllib.parse.urlsplit(normalized)
    host = parsed.hostname or ""
    match = LDXP_PATH.fullmatch(parsed.path.rstrip("/"))
    if host in LDXP_HOSTS and match:
        token = urllib.parse.unquote(match.group(1)).strip()
        canonical_host = "wzyp.cn" if host in {"wzyp.cn", "www.wzyp.cn"} else "pay.ldxp.cn"
        source_url = f"https://{canonical_host}/shop/{urllib.parse.quote(token, safe='._~-')}"
        return ProbeResult("ldxp", source_url, token.casefold())

    match = PLATFORM_16688_PATH.fullmatch(parsed.path.rstrip("/"))
    if host in PLATFORM_16688_HOSTS and match:
        shop_no = urllib.parse.unquote(match.group(1)).strip()
        return _probe_16688(parsed, shop_no, client)

    origin = urllib.parse.urlunsplit(("https", parsed.netloc, "", "", ""))
    try:
        config = _json(client.get(f"{origin}/api/v1/public/config", accept="application/json"))
        products = _json(client.get(
            f"{origin}/api/v1/public/products?page=1&page_size=1",
            accept="application/json",
        ))
        if (
            isinstance(config, dict)
            and config.get("status_code") == 0
            and isinstance(config.get("data"), dict)
            and isinstance(products, dict)
            and products.get("status_code") == 0
            and isinstance(products.get("data"), list)
            and isinstance(products.get("pagination"), dict)
        ):
            data = config["data"]
            brand = data.get("brand") if isinstance(data.get("brand"), dict) else {}
            shop_name = str(brand.get("site_name") or data.get("site_name") or host).strip()
            total = products["pagination"].get("total")
            product_count = int(total) if total not in (None, "") else len(products["data"])
            return ProbeResult("dujiao_next", origin, origin, shop_name, product_count)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    try:
        woo_response = client.get(
            f"{origin}/wp-json/wc/store/v1/products?page=1&per_page=1",
            accept="application/json",
        )
        products = _json(woo_response)
        if (
            isinstance(products, list)
            and bool(products)
            and all(isinstance(item, dict) for item in products)
            and all({"id", "name", "prices"}.issubset(item) for item in products)
        ):
            total = woo_response.headers.get("x-wp-total")
            product_count = int(total) if total not in (None, "") else len(products)
            return ProbeResult("woocommerce", origin, origin, host, product_count)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    try:
        document = _json(client.get(normalized, accept="application/json"))
        items = document if isinstance(document, list) else document.get("items") if isinstance(document, dict) else None
        if isinstance(items, list) and all(isinstance(item, dict) for item in items):
            name = ""
            if isinstance(document, dict) and isinstance(document.get("shop"), dict):
                name = str(document["shop"].get("name") or "").strip()
            token = "feed-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
            return ProbeResult("merchant_json", normalized, normalized, name, len(items))
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass

    page = client.get(normalized, accept="text/html,application/xhtml+xml")
    if page.status != 200:
        raise ValueError(f"source returned HTTP {page.status}")
    if product_count := _schema_product_count(page.body):
        return ProbeResult("schema_org", normalized, normalized, host, product_count)
    if sitemap_result := _schema_from_sitemap(
        origin,
        client,
        entry_url=normalized,
        preloaded=page,
    ):
        _page_url, product_count = sitemap_result
        return ProbeResult("schema_org", normalized, normalized, host, product_count)
    if sitemap_result := _schema_from_sitemap(origin, client):
        _page_url, product_count = sitemap_result
        return ProbeResult("schema_org", origin, origin, host, product_count)
    token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return ProbeResult("other", normalized, normalized, host, 0)
