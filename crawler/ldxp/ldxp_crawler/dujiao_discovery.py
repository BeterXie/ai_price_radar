from __future__ import annotations

import ipaddress
import json
import logging
import random
import re
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, Sequence

import requests
from price_radar_http import PinnedHTTPSClient, PinnedResponse

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
GITHUB_API_ORIGIN = "https://api.github.com"
GITHUB_REPOSITORY_QUERY = '"Dujiao-Next" in:name,description,readme is:public fork:true'
GITHUB_REPOSITORY_QUERIES = (
    GITHUB_REPOSITORY_QUERY,
    '"dujiao next" in:readme is:public',
    '"独角数卡" in:name,description,readme is:public',
)
GITHUB_MAX_PAGES = 10
GITHUB_MAX_CANDIDATES = 500
GITHUB_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
GITHUB_MAX_REQUEST_TIMEOUT = 30.0
GITHUB_EXCLUDED_HOSTS = frozenset({
    "github.com",
    "api.github.com",
    "githubusercontent.com",
    "githubassets.com",
    "example.com",
    "example.net",
    "example.org",
})
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


def normalize_github_homepage(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or any(ord(character) < 32 or ord(character) == 127 for character in raw):
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.fragment
        or port not in (None, 443)
    ):
        return None
    if (
        host in GITHUB_EXCLUDED_HOSTS
        or any(host.endswith("." + excluded) for excluded in GITHUB_EXCLUDED_HOSTS)
        or host.endswith(".example")
    ):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None
    try:
        normalized = PinnedHTTPSClient.normalize_url(raw)
    except (UnicodeError, ValueError):
        return None
    origin = normalize_candidate_origin(normalized)
    if not origin or is_excluded_origin(origin):
        return None
    return normalized


def validate_public_url(url: str) -> None:
    try:
        PinnedHTTPSClient.normalize_url(url)
    except ValueError as exc:
        raise ValueError("candidate must use public HTTPS on port 443") from exc


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


def read_limited_response(
    response: requests.Response,
    max_bytes: int = MAX_RESPONSE_BYTES,
    *,
    description: str = "candidate",
) -> bytes:
    limit_label = f"{max_bytes // (1024 * 1024)} MiB" if max_bytes % (1024 * 1024) == 0 else f"{max_bytes} bytes"
    try:
        content_length = int(response.headers.get("Content-Length") or 0)
    except (TypeError, ValueError):
        content_length = 0
    if content_length > max_bytes:
        response.close()
        raise ValueError(f"{description} response exceeds {limit_label}")

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"{description} response exceeds {limit_label}")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        response.close()


def _decode_body(response: requests.Response, body: bytes) -> str:
    return body.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")


class _InjectedSessionClient:
    """Adapter used only by injected unit-test transports."""

    def __init__(self, session: Any, timeout: float):
        self.session = session
        self.timeout = timeout

    def get(self, url: str, *, accept: str) -> PinnedResponse:
        response = self.session.get(
            url,
            headers={"Accept": accept},
            timeout=self.timeout,
            allow_redirects=False,
            stream=True,
        )
        if 300 <= response.status_code < 400:
            response.close()
            raise ValueError("source redirects are not followed")
        body = read_limited_response(response)
        return PinnedResponse(
            response.status_code,
            {str(key).casefold(): str(value) for key, value in response.headers.items()},
            body,
        )


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
        candidate_client_factory: Callable[[], Any] | None = None,
    ):
        self.session = session
        self.timeout = timeout
        self.max_pages = max(1, min(max_pages, 20))
        self.rate_limiter = GlobalRateLimiter(request_interval)
        if candidate_client_factory is not None:
            self.candidate_client_factory = candidate_client_factory
        elif isinstance(session, requests.Session):
            self.candidate_client_factory = lambda: PinnedHTTPSClient(
                max_response_bytes=MAX_RESPONSE_BYTES,
                max_task_bytes=(self.max_pages + 2) * MAX_RESPONSE_BYTES,
                max_task_seconds=max(30.0, timeout * (self.max_pages + 2)),
                request_timeout=timeout,
                user_agent="AI-Price-Radar-Dujiao-Discovery/1",
            )
        else:
            self.candidate_client_factory = lambda: _InjectedSessionClient(session, timeout)
        self._candidate_client: Any | None = None

    def _get(self, url: str, *, accept: str) -> tuple[PinnedResponse, bytes]:
        validate_public_url(url)
        self.rate_limiter.wait()
        if self._candidate_client is None:
            raise RuntimeError("candidate client is not initialized")
        response = self._candidate_client.get(url, accept=accept)
        return response, response.body

    def _home(self, origin: str) -> tuple[str, PinnedResponse, bytes]:
        url = origin + "/"
        response, body = self._get(url, accept="text/html,application/xhtml+xml")
        return normalize_candidate_origin(url) or origin, response, body

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
            self._candidate_client = self.candidate_client_factory()
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
        except (requests.RequestException, OSError, ValueError) as exc:
            result.status = "validation_failed"
            result.error = str(exc)[:500]
        finally:
            self._candidate_client = None
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

    def from_github(
        self,
        keywords: Sequence[str],
        *,
        pages: int,
        count: int,
        max_candidates: int,
        timeout: float,
        github_token: str = "",
    ) -> int:
        page_limit = min(max(1, pages), GITHUB_MAX_PAGES)
        per_page = min(max(1, count), 100)
        candidate_limit = min(max(0, max_candidates), GITHUB_MAX_CANDIDATES)
        request_timeout = min(max(1.0, timeout), GITHUB_MAX_REQUEST_TIMEOUT)
        if candidate_limit == 0:
            return 0

        found = 0
        fetched_repositories = 0
        submitted_origins: set[str] = set()
        filter_keywords = merge_unique([*DEFAULT_AI_KEYWORDS, *keywords])
        pages_remaining = page_limit
        for query in GITHUB_REPOSITORY_QUERIES:
            if pages_remaining <= 0 or self.reached_limit():
                break
            stopped = False
            for page in range(1, min(pages_remaining, page_limit) + 1):
                if self.reached_limit():
                    break
                params = {
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                }
                url = GITHUB_API_ORIGIN + "/search/repositories?" + urllib.parse.urlencode(params)
                headers = {
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                if github_token:
                    headers["Authorization"] = f"Bearer {github_token}"
                try:
                    response = self.verifier.session.get(
                        url,
                        headers=headers,
                        timeout=request_timeout,
                        allow_redirects=False,
                        stream=True,
                    )
                    body = read_limited_response(
                        response,
                        GITHUB_MAX_RESPONSE_BYTES,
                        description="GitHub API",
                    )
                except (requests.RequestException, OSError, ValueError) as exc:
                    self.logger.warning("Dujiao GitHub API 请求失败（%s）", type(exc).__name__)
                    stopped = True
                    break
                pages_remaining -= 1
                if response.status_code in {403, 429}:
                    self.logger.warning(
                        "Dujiao GitHub API 限流（HTTP %s，remaining=%s）",
                        response.status_code,
                        response.headers.get("X-RateLimit-Remaining", "unknown"),
                    )
                    stopped = True
                    break
                if response.status_code != 200:
                    self.logger.warning("Dujiao GitHub API HTTP %s", response.status_code)
                    stopped = True
                    break
                try:
                    document = json.loads(body.decode("utf-8"))
                    items = document.get("items")
                    total_count = int(document.get("total_count"))
                except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
                    self.logger.warning("Dujiao GitHub API 响应无效（%s）", type(exc).__name__)
                    stopped = True
                    break
                if not isinstance(items, list) or total_count < 0:
                    self.logger.warning("Dujiao GitHub API 响应缺少有效仓库列表")
                    stopped = True
                    break

                fetched_repositories += len(items)
                for item in items:
                    if not isinstance(item, dict) or item.get("private") is True:
                        continue
                    homepage = normalize_github_homepage(item.get("homepage"))
                    origin = normalize_candidate_origin(homepage or "")
                    if not homepage or not origin:
                        continue
                    if origin not in submitted_origins:
                        if len(submitted_origins) >= candidate_limit:
                            return found
                        submitted_origins.add(origin)
                    repository = str(item.get("full_name") or "").strip()[:100]
                    source = f"github:{repository}" if repository else "github:repository-homepage"
                    found += int(self.add_url(homepage, source, filter_keywords))
                    if self.reached_limit():
                        return found
                if len(submitted_origins) >= candidate_limit:
                    return found
                if not items or fetched_repositories >= min(total_count, 1000):
                    break
            if stopped:
                break
        return found
