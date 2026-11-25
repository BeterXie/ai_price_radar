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
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlsplit

from price_radar_http import PinnedHTTPSClient

from .base import SourceFetchError, validate_record


name = "kmdian"
API_URL = "https://www.kmdian.com/api/v1/open/products"
API_KEY_ENV = "KMDIAN_API_KEY"
PAGE_SIZE = 20
MAX_PAGES = 500
MAX_TASK_SECONDS = 1500  # Leave time for publication within the 30-minute host job.
REQUEST_INTERVAL_SECONDS = 1.1  # Below the platform's 60 requests/minute/key limit.
CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,100}")
RAW_FIELDS = frozenset({
    "shop_name", "shop_url", "shop_code", "goods_no", "title", "product_url",
    "price_cent", "stock", "sales_count", "cover", "updated_at",
})


class _DescriptionImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "img" or len(self.images) >= 12:
            return
        src = dict(attrs).get("src") or ""
        if len(src) > 2000:
            return
        try:
            parsed = urlsplit(src)
        except ValueError:
            return
        if (len(src) <= 2000 and parsed.scheme == "https" and parsed.hostname == "img.kmdian.com"
                and parsed.netloc == "img.kmdian.com" and src not in self.images):
            self.images.append(src)


def _enrich_detail(record: dict[str, Any], client: PinnedHTTPSClient, api_key: str) -> None:
    goods_no = record["variant_key"]
    try:
        # Public storefront API: never forward the privileged platform key.
        response = client.get(f"https://www.kmdian.com/api/v1/products/{goods_no}", accept="application/json")
    except ssl.SSLCertVerificationError:
        raise
    except (OSError, http.client.HTTPException):
        raise SourceFetchError("kmdian product detail request failed") from None
    if response.status != 200:
        raise SourceFetchError(f"kmdian product detail returned HTTP {response.status}")
    try:
        document = json.loads(response.body)
        data = document["data"]
        product, shop = data["product"], data["shop"]
        if type(document.get("code")) is not int or document["code"] != 0:
            raise ValueError("invalid response code")
        if product["goods_no"] != goods_no or shop["shop_code"] != record["raw_json"]["shop_code"]:
            raise ValueError("mismatched identity")
        description = product.get("description")
        usage = product.get("usage_note")
        category = data.get("category_name")
        description = "" if description is None else description
        usage = "" if usage is None else usage
        category = "" if category is None else category
        if not all(isinstance(value, str) for value in (description, usage, category)):
            raise ValueError("invalid content types")
        if len(description) + len(usage) > 200_000 or api_key in description + usage + category:
            raise ValueError("invalid public content")
    except (KeyError, TypeError, ValueError):
        raise ValueError("kmdian product detail identity or public content is invalid") from None
    description = description + ("\n" + usage if usage else "")
    parser = _DescriptionImages()
    parser.feed(description)
    decoded = unescape(description)
    if any(api_key in value for value in (decoded, re.sub(r'<[^>]*>', '', decoded), *parser.images)):
        raise ValueError("kmdian detail contains the API credential")
    record["raw_json"].update(description=description, description_images=parser.images)
    record["category_name"] = category


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
    for field, kind, identifier in (("shop_url", "shop", item['shop_code']), ("product_url", "item", item['goods_no'])):
        parsed = urlsplit(PinnedHTTPSClient.normalize_url(item[field]))
        if parsed.netloc not in {'kmdian.com','www.kmdian.com'} or parsed.path != f'/{kind}/{identifier}' or parsed.query:
            raise ValueError("kmdian public URL does not match platform identity")
    stock = None if item.get("stock") is None else _integer(item["stock"], "stock")
    price_cent = _integer(item.get("price_cent"), "price_cent")
    encoded_item = json.dumps(item, ensure_ascii=False, default=str)
    if json.dumps(api_key, ensure_ascii=False)[1:-1] in encoded_item:
        raise ValueError("kmdian response contains the API credential")
    for key in ("cover", "updated_at"):
        if item.get(key) is not None and not isinstance(item[key], str):
            raise ValueError(f"kmdian {key} must be a string")
    if item.get("sales_count") is not None:
        _integer(item["sales_count"], "sales_count")
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
        max_task_seconds=MAX_TASK_SECONDS,
        request_timeout=20,
        user_agent="AI-Price-Radar-Importer/1",
    )
    next_request_at = time.monotonic()
    deadline = next_request_at + MAX_TASK_SECONDS

    def read_pass() -> tuple[list[dict[str, Any]], int]:
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
                return records, page
        raise ValueError("kmdian API exceeded the page limit")

    first_pass, first_pages = read_pass()
    # The API exposes no snapshot/version token. For a multi-page response,
    # read it twice and only permit stale-offer pruning when the complete
    # product identity set agrees across both passes.
    records = first_pass
    if first_pages != 1:
        first_ids = {(row["token"], row["product_key"]) for row in first_pass}
        del first_pass
        records, _second_pages = read_pass()
        second_ids = {(row["token"], row["product_key"]) for row in records}
        if first_ids != second_ids:
            raise ValueError("kmdian catalog changed during pagination; retry the complete import")
    cache_root = os.getenv('KMDIAN_DETAIL_CACHE_DIR','').strip()
    if not cache_root and os.getenv('COLLECTOR_RESULTS_DIR','').strip():
        cache_root = str(Path(os.environ['COLLECTOR_RESULTS_DIR'])/'kmdian-details')
    cache_dir = Path(cache_root) if cache_root else None
    if cache_dir:
        cache_dir.mkdir(parents=True,exist_ok=True)
        active_files = {r['variant_key']+'.json' for r in records}
        for old in cache_dir.glob('*.json'):
            if old.name not in active_files or time.time()-old.stat().st_mtime > 6*3600:
                old.unlink()
    for index, record in enumerate(records):
        # The existing private result volume lets a later job resume verified
        # detail work when a large catalog reaches the bounded task deadline.
        cache_file = cache_dir / (record['variant_key']+'.json') if cache_dir else None
        signature = [record['variant_key'],record['raw_json']['shop_code'],record['raw_json'].get('updated_at')]
        if cache_file and cache_file.is_file() and cache_file.stat().st_size <= 1024*1024:
            try:
                cached = json.loads(cache_file.read_text(encoding='utf-8'))
                raw = cached['raw_json']
                if not isinstance(raw, dict):
                    raise ValueError('invalid cached detail')
                if (cached['identity']==signature and time.time()-cached['saved_at'] < 6*3600
                        and isinstance(raw.get('description'),str) and isinstance(raw.get('description_images'),list)
                        and isinstance(cached.get('category_name'),str) and api_key not in json.dumps(cached)):
                    record['raw_json'].update({k:raw[k] for k in ('description','description_images')})
                    record['category_name']=cached['category_name']
                    yield record
                    records[index] = None
                    continue
            except (OSError,ValueError,KeyError,TypeError):
                pass
        if time.monotonic() + 22 >= deadline:
            raise SourceFetchError('kmdian detail budget reached' + ('; verified details retained for the next job' if cache_dir else '; configure a private KMDIAN_DETAIL_CACHE_DIR to resume'))
        delay = next_request_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        next_request_at = time.monotonic() + REQUEST_INTERVAL_SECONDS
        # Independent per-product bounds prevent detail traffic from exhausting
        # the credentialed list client's cumulative byte/time budget.
        detail_client = PinnedHTTPSClient(max_response_bytes=1024*1024,max_task_bytes=1024*1024,
            max_task_seconds=20,request_timeout=20,user_agent='AI-Price-Radar-Importer/1')
        _enrich_detail(record, detail_client, api_key)
        if cache_file:
            cache_file.parent.mkdir(parents=True,exist_ok=True)
            temp = cache_file.with_suffix('.tmp')
            temp.write_text(json.dumps({'identity':signature,'saved_at':time.time(),'category_name':record['category_name'],
                'raw_json':{k:record['raw_json'][k] for k in ('description','description_images')}},ensure_ascii=False),encoding='utf-8')
            temp.replace(cache_file)
        yield record
        records[index] = None
