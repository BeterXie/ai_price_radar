from __future__ import annotations

import ipaddress
import json
import logging
import random
import re
import socket
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Sequence

import requests

from .db import StateDB
from .utils import GlobalRateLimiter, merge_unique, utc_now


DEFAULT_AI_KEYWORDS = (
    "chatgpt",
    "gpt plus",
    "gptplus",
    "openai",
    "codex",
    "claude",
    "gemini",
    "grok",
    "cursor",
    "augment",
)
HOME_FINGERPRINTS = (
    ("dujiao-next", "dujiao-next"),
    ("professional-online-studio", "professional online studio providing quality products"),
    ("featured-products", "featured products"),
    ("premium-digital-assets", "discover our premium collection of digital assets"),
)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
TITLE_RE = re.compile(r"<title(?:\s[^>]*)?>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class DujiaoVerificationResult:
    origin: str
    discovered_by: str
    discovered_url: str
    status: str
    fingerprints: list[str] = field(default_factory=list)
    api_verified: bool = False
    product_count: int | None = None
    matched_products: list[dict[str, Any]] = field(default_factory=list)
    site_name: str = ""
    last_verified_at: str = field(default_factory=utc_now)
    error: str = ""


def _netloc(host: str, port: int | None) -> str:
    rendered = f"[{host}]" if ":" in host else host
    return f"{rendered}:{port}" if port and port != 443 else rendered


def _normalized_https_url(value: str) -> str | None:
    value = str(value or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not host or parsed.username or parsed.password:
        return None
    return urllib.parse.urlunsplit(("https", _netloc(host, port), parsed.path or "/", parsed.query, ""))


def normalize_candidate_origin(value: str) -> str | None:
    normalized = _normalized_https_url(value)
    if not normalized:
        return None
    parsed = urllib.parse.urlsplit(normalized)
    return urllib.parse.urlunsplit(("https", parsed.netloc, "", "", ""))


def is_excluded_origin(origin: str) -> bool:
    host = (urllib.parse.urlsplit(origin).hostname or "").casefold().rstrip(".")
    return host == "dujiao-next.com" or host.endswith(".dujiao-next.com")


def validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("candidate must use public HTTPS")
    if host == "localhost" or host.endswith((".local", ".internal")):
        raise ValueError("candidate host must be public")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise ValueError("candidate host must be public")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("candidate host could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("candidate host resolves to a non-public address")


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


def _normalized_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s_\-—|/\\]+", " ", normalized).strip()


def _product_text(product: dict[str, Any]) -> str:
    category = product.get("category") if isinstance(product.get("category"), dict) else {}
    values = [
        _localized(product.get("title")),
        _localized(category.get("name")),
        " ".join(str(value) for value in product.get("tags", []) if value) if isinstance(product.get("tags"), list) else "",
    ]
    return _normalized_search_text(" ".join(values))


def read_limited_response(response: requests.Response, max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    try:
        content_length = int(response.headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        content_length = 0
    if content_length > max_bytes:
        response.close()
        raise ValueError("candidate response exceeds 5 MiB")

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("candidate response exceeds 5 MiB")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        response.close()


def _decode_body(response: requests.Response, body: bytes) -> str:
    return body.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")


def _site_name(home_text: str) -> str:
    match = TITLE_RE.search(home_text)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", " ", unescape(match.group(1)))
    return re.sub(r"\s+", " ", title).strip()[:200]


class DujiaoVerifier:
    def __init__(
        self,
        session: requests.Session,
        *,
        timeout: float,
        request_interval: float,
        max_pages: int = 5,
    ):
        self.session = session
        self.timeout = timeout
        self.max_pages = max(1, min(max_pages, 20))
        self.rate_limiter = GlobalRateLimiter(request_interval)

    def _get(self, url: str, *, accept: str) -> tuple[requests.Response, bytes]:
        validate_public_url(url)
        self.rate_limiter.wait()
        response = self.session.get(
            url,
            headers={"Accept": accept},
            timeout=self.timeout,
            allow_redirects=False,
            stream=True,
        )
        return response, read_limited_response(response)

    def _home(self, origin: str) -> tuple[str, requests.Response, bytes]:
        url = origin + "/"
        for _ in range(3):
            response, body = self._get(url, accept="text/html,application/xhtml+xml")
            if response.status_code not in REDIRECT_STATUSES:
                return normalize_candidate_origin(url) or origin, response, body
            location = response.headers.get("Location") or ""
            target = urllib.parse.urljoin(url, location)
            target_origin = normalize_candidate_origin(target)
            if not target_origin or is_excluded_origin(target_origin):
                raise ValueError("candidate redirected to an invalid origin")
            if target_origin != origin:
                raise ValueError("candidate redirected to a different origin")
            validate_public_url(target)
            url = target
        raise ValueError("candidate redirects exceeded limit")

    def _products_page(self, origin: str, page: int) -> tuple[list[dict[str, Any]], int | None, int]:
        query = urllib.parse.urlencode({"page": page, "page_size": 100})
        url = f"{origin}/api/v1/public/products?{query}"
        response, body = self._get(url, accept="application/json")
        if response.status_code != 200:
            raise ValueError(f"product API returned HTTP {response.status_code}")
        try:
            document = json.loads(_decode_body(response, body))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("product API did not return JSON") from exc
        if not isinstance(document, dict) or document.get("status_code") != 0 or not isinstance(document.get("data"), list):
            raise ValueError("product API response is not Dujiao-Next public data")
        pagination = document.get("pagination")
        if not isinstance(pagination, dict):
            raise ValueError("product API response missing pagination")
        try:
            response_page = int(pagination.get("page"))
            total_page = int(pagination.get("total_page"))
            total = int(pagination.get("total")) if pagination.get("total") is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("product API pagination is invalid") from exc
        items = document["data"]
        if response_page != page or total_page < 0 or total_page > 10_000 or (page > 1 and total_page < page):
            raise ValueError("product API pagination is invalid")
        if total is not None and total < 0:
            raise ValueError("product API pagination is invalid")
        if total_page == 0 and items:
            raise ValueError("product API pagination is inconsistent")
        return [item for item in items if isinstance(item, dict)], total, total_page

    def verify(
        self,
        discovered_url: str,
        *,
        discovered_by: str,
        keywords: Sequence[str] = DEFAULT_AI_KEYWORDS,
    ) -> DujiaoVerificationResult:
        normalized_url = _normalized_https_url(discovered_url) or str(discovered_url).strip()
        origin = normalize_candidate_origin(discovered_url) or ""
        result = DujiaoVerificationResult(
            origin=origin,
            discovered_by=discovered_by,
            discovered_url=normalized_url,
            status="validation_failed",
        )
        if not origin:
            result.status = "invalid_url"
            result.error = "candidate URL is invalid"
            return result
        if is_excluded_origin(origin):
            result.status = "excluded"
            return result

        try:
            origin, home, home_body = self._home(origin)
            result.origin = origin
            if home.status_code != 200:
                raise ValueError(f"homepage returned HTTP {home.status_code}")
            decoded_home = _decode_body(home, home_body)
            home_text = decoded_home.casefold()
            result.site_name = _site_name(decoded_home)
            result.fingerprints = [name for name, marker in HOME_FINGERPRINTS if marker in home_text]

            page = 1
            fetched = 0
            total_pages = 1
            limited = False
            keywords = tuple(_normalized_search_text(value) for value in keywords if value.strip())
            while page <= total_pages:
                items, total, total_pages = self._products_page(origin, page)
                result.api_verified = True
                fetched += len(items)
                if result.product_count is None:
                    result.product_count = total
                for product in items:
                    slug = str(product.get("slug") or "").strip()
                    name = _localized(product.get("title"))
                    matched = [keyword for keyword in keywords if keyword in _product_text(product)]
                    if slug and name and matched:
                        result.matched_products.append({
                            "slug": slug,
                            "name": name,
                            "url": f"{origin}/products/{urllib.parse.quote(slug, safe='')}",
                            "matched_keywords": matched,
                        })
                if result.matched_products or total_pages == 0 or page >= total_pages:
                    break
                if page >= self.max_pages:
                    limited = True
                    break
                page += 1
            if result.product_count is None:
                result.product_count = fetched

            if result.product_count <= 0:
                result.status = "no_products"
            elif result.matched_products:
                result.status = "pending_review"
            elif limited:
                result.status = "scan_limited"
            else:
                result.status = "no_match"
        except (requests.RequestException, ValueError) as exc:
            result.status = "validation_failed"
            result.error = str(exc)[:500]
        result.last_verified_at = utc_now()
        return result


def bing_queries(keywords: Sequence[str]) -> list[str]:
    queries = [
        '"Dujiao-Next" "Featured Products"',
        '"Dujiao-Next" "Professional online studio"',
        '"Dujiao-Next" "自动发货"',
        'inurl:/products "Dujiao-Next"',
    ]
    queries.extend(f'"{keyword}" "Dujiao-Next"' for keyword in keywords if str(keyword).strip())
    return merge_unique(queries)


def extract_bing_result_urls(content: bytes) -> list[str]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    return merge_unique(item.findtext("link") or "" for item in root.findall(".//item"))


class DujiaoDiscovery:
    def __init__(
        self,
        db: StateDB,
        verifier: DujiaoVerifier,
        *,
        logger: logging.Logger,
        max_new_candidates: int,
        max_processed_candidates: int,
        reverify_stale_hours: float,
    ):
        self.db = db
        self.verifier = verifier
        self.logger = logger
        self.max_new_candidates = max_new_candidates
        self.max_processed_candidates = max_processed_candidates
        self.reverify_stale_hours = reverify_stale_hours
        self.processed_count = 0
        self.new_candidate_count = 0
        self._seen_results: dict[str, DujiaoVerificationResult] = {}

    def reached_limit(self) -> bool:
        return self.max_processed_candidates > 0 and self.processed_count >= self.max_processed_candidates

    def reached_new_limit(self) -> bool:
        return self.max_new_candidates > 0 and self.new_candidate_count >= self.max_new_candidates

    def _stale_before(self) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(0.0, self.reverify_stale_hours))
        return cutoff.replace(microsecond=0).isoformat()

    def add_url(
        self,
        url: str,
        source: str,
        keywords: Sequence[str] = DEFAULT_AI_KEYWORDS,
        *,
        force_reverify: bool = False,
    ) -> bool:
        origin = normalize_candidate_origin(url)
        if not origin or is_excluded_origin(origin):
            return False
        normalized_url = _normalized_https_url(url) or str(url).strip()
        previous = self._seen_results.get(origin)
        if previous:
            result = replace(
                previous,
                discovered_by=source,
                discovered_url=normalized_url,
            )
        else:
            existing = self.db.get_dujiao_candidate(origin)
            if existing is not None and not force_reverify and existing["last_verified_at"] > self._stale_before():
                self.db.record_dujiao_discovery(origin, normalized_url, source)
                return False
            if existing is None and self.reached_new_limit():
                return False
            if self.reached_limit():
                return False
            result = self.verifier.verify(url, discovered_by=source, keywords=keywords)
            self.processed_count += 1
        self._seen_results[origin] = result
        if result.origin:
            self._seen_results[result.origin] = result
        inserted = self.db.upsert_dujiao_candidate(result)
        if inserted:
            self.new_candidate_count += 1
        self.logger.info(
            "Dujiao 候选 %s 状态=%s 商品=%s AI命中=%s 来源=%s",
            result.origin,
            result.status,
            result.product_count,
            len(result.matched_products),
            source[:100],
        )
        return inserted

    def reverify_stale(self, keywords: Sequence[str] = DEFAULT_AI_KEYWORDS) -> int:
        verified = 0
        remaining = (
            max(0, self.max_processed_candidates - self.processed_count)
            if self.max_processed_candidates > 0
            else None
        )
        for row in self.db.list_stale_dujiao_candidates(self._stale_before(), limit=remaining):
            if self.reached_limit():
                break
            before = self.processed_count
            self.add_url(row["origin"], "stale-reverify", keywords, force_reverify=True)
            verified += int(self.processed_count > before)
        return verified

    def from_seeds(self, seeds: Sequence[str], seed_file: Path | None, keywords: Sequence[str]) -> int:
        values = list(seeds)
        if seed_file and seed_file.exists():
            values.extend(
                line.strip()
                for line in seed_file.read_text("utf-8-sig", errors="ignore").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
        found = 0
        for value in values:
            if self.reached_limit():
                break
            found += int(self.add_url(value, "seed", keywords))
        return found

    def from_bing(self, keywords: Sequence[str], *, pages: int, count: int, delay: float) -> int:
        found = 0
        filter_keywords = merge_unique([*DEFAULT_AI_KEYWORDS, *keywords])
        for query in bing_queries(keywords):
            if self.reached_limit():
                break
            for page in range(max(1, pages)):
                params = {
                    "q": query,
                    "format": "rss",
                    "count": min(max(count, 10), 50),
                    "first": 1 + page * count,
                    "setlang": "zh-Hans",
                }
                url = "https://www.bing.com/search?" + urllib.parse.urlencode(params)
                try:
                    response = self.verifier.session.get(url, timeout=self.verifier.timeout)
                except requests.RequestException as exc:
                    self.logger.warning("Dujiao Bing 请求失败：%s", exc)
                    break
                if response.status_code != 200:
                    self.logger.warning("Dujiao Bing HTTP %s：%s", response.status_code, query)
                    break
                urls = extract_bing_result_urls(response.content)
                if not urls:
                    break
                for candidate_url in urls:
                    found += int(self.add_url(candidate_url, f"bing:{query}", filter_keywords))
                    if self.reached_limit():
                        break
                time.sleep(max(0.0, delay) + random.uniform(0, 0.4))
        return found
