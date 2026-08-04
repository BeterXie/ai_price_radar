from __future__ import annotations

import hashlib
import logging
import random
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Sequence

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import ProductMatch, ShopScanResult
from .sensitive_data import redact_text, sensitive_hits
from .utils import CLOSED_RE, GlobalRateLimiter, clean_text, safe_float, safe_http_url


SYMBOL_PRICE_RE = re.compile(r"[¥￥]\s*(\d+(?:\.\d{1,2})?)")
BARE_PRICE_RE = re.compile(r"(\d+(?:\.\d{1,2})?)")
LOGIN_REQUIRED_RE = re.compile(
    r"登录|login|sign\s*in|请先登录|手机号登录|验证登录",
    re.IGNORECASE,
)
CHALLENGE_RE = re.compile(
    r"verification|captcha|challenge|人机验证|安全验证|滑块验证|请完成验证|访问验证|阿里云验证码",
    re.IGNORECASE,
)
IN_STOCK_RE = re.compile(r"有货|库存|in\s*stock|available", re.IGNORECASE)
OUT_OF_STOCK_RE = re.compile(r"缺货|售罄|已售完|out\s*of\s*stock|sold\s*out", re.IGNORECASE)
UNAVAILABLE_RE = re.compile(r"下架|已下架|不可用|unavailable", re.IGNORECASE)

SELECTOR_VERSION = "ldxp-dom-v1"


def parse_public_price(text: str, price_element_text: str = "") -> Optional[float]:
    """Extract the public price from a card.

    A price with an explicit currency symbol wins; otherwise the dedicated price
    element is used. Arbitrary card text is never scanned for bare numbers, so
    version numbers such as ``GPT-4`` or day counts are not misread as prices.
    """
    symbol_match = SYMBOL_PRICE_RE.search(clean_text(text))
    if symbol_match:
        return safe_float(symbol_match.group(1))
    if price_element_text:
        element = clean_text(price_element_text)
        symbol_match = SYMBOL_PRICE_RE.search(element)
        if symbol_match:
            return safe_float(symbol_match.group(1))
        bare_match = BARE_PRICE_RE.search(element)
        if bare_match:
            return safe_float(bare_match.group(1))
    return None


def parse_public_stock(text: str) -> str:
    lowered = clean_text(text).casefold()
    if UNAVAILABLE_RE.search(lowered):
        return "unavailable"
    if OUT_OF_STOCK_RE.search(lowered):
        return "out_of_stock"
    if IN_STOCK_RE.search(lowered):
        return "in_stock"
    return "unknown"


def is_challenge_text(text: str) -> bool:
    return bool(CHALLENGE_RE.search(clean_text(text)))


def is_login_required_text(text: str) -> bool:
    return bool(LOGIN_REQUIRED_RE.search(clean_text(text)))


def content_hash(*values: object) -> str:
    payload = "|".join(str(value or "").strip() for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_product_url(value: str, base_url: str) -> str:
    url = clean_text(value)
    if url.startswith("/"):
        url = urllib.parse.urljoin(base_url, url)
    return safe_http_url(url) or ""


def build_product_match(
    *,
    product_key: str,
    name: str,
    price: Optional[float],
    stock: str,
    product_url: str,
    shop_closed: bool,
    keywords: Sequence[str],
) -> Optional[ProductMatch]:
    """Build a minimal ProductMatch; returns None when sensitive data is detected."""
    redacted_name, hits = redact_text(name)
    if hits:
        return None
    if not redacted_name:
        return None
    normalized_name = clean_text(redacted_name).casefold()
    hit = [kw for kw in keywords if kw and clean_text(kw).casefold() in normalized_name]
    if not hit:
        return None
    if shop_closed:
        status = "店铺暂停营业"
    elif stock == "unavailable":
        status = "下架/不可用"
    elif stock == "out_of_stock":
        status = "缺货"
    elif stock == "in_stock":
        status = "有货"
    else:
        status = "库存未知"
    return ProductMatch(
        product_key=product_key,
        product_name=redacted_name,
        matched_keywords=hit,
        listed_price=price,
        stock_count=0 if status == "缺货" else None,
        product_status=status,
        product_url=product_url,
        content_hash=content_hash(redacted_name, price, stock, product_url),
    )


class PublicDomScanner:
    """Anonymous, stateless public DOM collector.

    No persistent profile, no storage state, no cookie or browser storage restore,
    no internal API replay and no sensitive header reuse. Stops immediately on
    403/429/challenge/login and never retries challenge pages.
    """

    def __init__(
        self,
        *,
        executable_path: Optional[Path] = None,
        timeout: float = 35.0,
        page_wait: float = 2.0,
        request_interval: float = 5.0,
        request_jitter_seconds: float = 2.0,
        max_requests_per_shop: int = 8,
        logger: logging.Logger,
    ):
        self.executable_path = executable_path
        self.timeout_ms = int(max(5, timeout) * 1000)
        self.page_wait_ms = int(max(0, page_wait) * 1000)
        self.rate_limiter = GlobalRateLimiter(request_interval)
        self.request_jitter_seconds = max(0.0, request_jitter_seconds)
        self.max_requests_per_shop = max(1, max_requests_per_shop)
        self.logger = logger
        self._pw: Any = None
        self._browser: Any = None

    def __enter__(self) -> "PublicDomScanner":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            executable_path=str(self.executable_path) if self.executable_path else None,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _anonymous_context(self) -> Any:
        assert self._browser is not None
        return self._browser.new_context(
            locale="zh-CN",
            java_script_enabled=True,
            accept_downloads=False,
        )

    def scan_shop(self, candidate: Any, keywords: Sequence[str]) -> ShopScanResult:
        token = candidate["token"]
        shop_url = clean_text(candidate.get("url") or "")
        self.rate_limiter.wait()
        if self.request_jitter_seconds:
            time.sleep(random.uniform(0, self.request_jitter_seconds))
        context = self._anonymous_context()
        page = context.new_page()
        request_count = {"n": 0}

        def on_request(_request: Any) -> None:
            request_count["n"] += 1

        page.on("request", on_request)
        try:
            page.set_default_timeout(self.timeout_ms)
            page.set_default_navigation_timeout(self.timeout_ms)
            try:
                nav_response = page.goto(shop_url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError as exc:
                return ShopScanResult(token, "network_error", shop_url=shop_url, error=f"页面打开超时：{exc}", engine="public_dom")
            except Exception as exc:
                return ShopScanResult(token, "network_error", shop_url=shop_url, error=f"页面打开失败：{exc}", engine="public_dom")
            if request_count["n"] > self.max_requests_per_shop:
                return ShopScanResult(token, "budget_deferred", shop_url=shop_url, error="per-shop request budget reached", engine="public_dom")

            nav_status = nav_response.status if nav_response else None
            if nav_status == 429:
                return ShopScanResult(token, "rate_limited", shop_url=shop_url, http_status=429, engine="public_dom")
            if self.page_wait_ms:
                page.wait_for_timeout(self.page_wait_ms)

            body_text = self._body_text(page)
            if is_login_required_text(body_text):
                return ShopScanResult(token, "unsupported", shop_url=shop_url, error="登录要求，永久停止自动扫描", engine="public_dom")
            if nav_status == 403 or is_challenge_text(body_text):
                status = "challenge_required" if is_challenge_text(body_text) else "blocked"
                return ShopScanResult(
                    token,
                    status,
                    shop_url=shop_url,
                    error="检测到验证/阻断页面，不自动重试",
                    http_status=nav_status or 403,
                    engine="public_dom",
                )
            if nav_status and nav_status >= 400:
                return ShopScanResult(
                    token,
                    "blocked" if nav_status == 403 else "failed",
                    shop_url=shop_url,
                    error=f"页面返回 HTTP {nav_status}",
                    http_status=nav_status,
                    engine="public_dom",
                )

            rows = self._dom_product_rows(page)
            shop_closed = bool(CLOSED_RE.search(body_text))
            products = [row for row in rows if isinstance(row, dict)]
            if not products:
                return ShopScanResult(
                    token,
                    "unsupported",
                    shop_url=shop_url,
                    error="页面无公开商品卡片，不探测内部接口",
                    engine="public_dom",
                )

            matches: list[ProductMatch] = []
            for row in products:
                name = clean_text(row.get("name") or "")
                raw_url = clean_text(row.get("link") or "")
                product_url = _safe_product_url(raw_url, shop_url)
                price = parse_public_price(row.get("text") or name, row.get("price_text") or "")
                stock = parse_public_stock(row.get("text") or "")
                product_key = clean_text(row.get("product_key") or product_url or name)[:300]
                match = build_product_match(
                    product_key=product_key,
                    name=name,
                    price=price,
                    stock=stock,
                    product_url=product_url,
                    shop_closed=shop_closed,
                    keywords=keywords,
                )
                if match is not None:
                    matches.append(match)

            if shop_closed:
                status = "closed"
            elif not matches:
                status = "no_match"
            else:
                status = "success"
            return ShopScanResult(
                token=token,
                status=status,
                shop_name=clean_text(candidate.get("shop_name") or ""),
                shop_url=shop_url,
                scanned_item_count=len(products),
                matches=matches,
                http_status=nav_status,
                engine="public_dom",
            )
        finally:
            page.close()
            context.close()

    @staticmethod
    def _body_text(page: Any) -> str:
        try:
            return clean_text(page.locator("body").inner_text(timeout=3000))
        except Exception:
            return ""

    @staticmethod
    def _dom_product_rows(page: Any) -> list[dict[str, Any]]:
        try:
            rows = page.evaluate(
                r"""
                () => Array.from(document.querySelectorAll('a[href*="/item/"]')).map(a => {
                  const box = a.closest('article,li,[class*="goods"],[class*="product"],[class*="item"],div') || a;
                  const text = (box.innerText || a.innerText || a.textContent || '').trim();
                  const lines = text.split(/\n+/).map(x => x.trim()).filter(Boolean);
                  const priceNode = box.querySelector('[class*="price"],[class*="amount"],.price,.amount');
                  const priceText = priceNode ? (priceNode.innerText || '').trim() : '';
                  const name = (a.getAttribute('title') || lines.find(x => !/^[¥￥]?\s*\d+(?:\.\d{1,2})?$/.test(x)) || '').trim();
                  const href = a.getAttribute('href') || '';
                  return {name, link: new URL(href, location.href).href, text, price_text: priceText, product_key: (href.match(/\/item\/([^/?]+)/) || [])[1] || ''};
                }).filter(x => x.name && x.link)
                """
            )
            return [row for row in rows if isinstance(row, dict)]
        except Exception:
            return []
