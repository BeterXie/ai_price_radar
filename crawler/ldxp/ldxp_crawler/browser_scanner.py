from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from playwright.sync_api import BrowserContext, Page, Playwright, Request, Response, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .models import ProductMatch, ShopScanResult
from .utils import (
    CHALLENGE_RE,
    CLOSED_RE,
    GlobalRateLimiter,
    JAVASCRIPT_CHALLENGE_RE,
    clean_text,
    merge_unique,
    normalize_shop_url,
    safe_float,
    safe_int,
    safe_http_url,
)

API_MARKER = "/shopApi/Shop/"
INFO_ENDPOINT = "/shopApi/Shop/info"
GOODS_ENDPOINT = "/shopApi/Shop/goodsList"
CATEGORY_ENDPOINT = "/shopApi/Shop/categoryList"
TARGET_BRAND_MARKERS = (
    "chatgpt",
    "openai",
    "gpt",
    "chatplus",
    "codex",
    "claude",
    "gemini",
    "googleoneai",
    "supergrok",
    "grok",
    "xai",
    "xpremium",
    "twitterblue",
)
IMPLICIT_CHATGPT_MARKERS = ("成品", "半成品", "首登")
NON_TARGET_PLUS_MARKERS = ("百度", "网盘", "小红书", "加速器", "梯子", "夸克", "迅雷", "youtube", "netflix", "spotify", "office", "wps")
GENERIC_EMAIL_MARKERS = ("gmail", "谷歌邮箱", "谷歌邮件", "谷歌账号", "outlook", "hotmail", "icloud", "ic邮箱", "微软邮箱")
CATEGORY_COMMERCE_MARKERS = ("plus", "pro", "team", "business", "max", "advanced", "ultra", "super", "heavy", "会员", "订阅", "代充", "直充", "充值", "接码", "api", "key", "token", "额度", "成品", "账号", "首登")


def normalize_identity(value: str) -> str:
    return re.sub(r"[\s_.\-—|/\\]+", "", value.casefold())


def has_target_brand(title: str, category: str = "") -> bool:
    title_identity = normalize_identity(title)
    category_identity = normalize_identity(category)
    x_premium = (
        "premium" in title_identity and "twitter" in title_identity
    ) or (
        "推特" in title_identity and any(marker in title_identity for marker in ("会员", "蓝v", "蓝标"))
    )
    if x_premium or any(marker in title_identity for marker in TARGET_BRAND_MARKERS):
        return True
    implicit_chatgpt = (
        "plus" in title_identity
        and any(marker in title_identity for marker in IMPLICIT_CHATGPT_MARKERS)
        and not any(marker in title_identity for marker in NON_TARGET_PLUS_MARKERS)
    )
    if implicit_chatgpt:
        return True
    return (
        any(marker in category_identity for marker in TARGET_BRAND_MARKERS)
        and not any(marker in title_identity for marker in GENERIC_EMAIL_MARKERS)
        and any(marker in title_identity for marker in CATEGORY_COMMERCE_MARKERS)
    )


class BrowserScanError(RuntimeError):
    def __init__(self, message: str, status: str = "failed", http_status: Optional[int] = None):
        super().__init__(message)
        self.status = status
        self.http_status = http_status


@dataclass
class RequestTemplate:
    url: str
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass
class CaptureState:
    templates: dict[str, RequestTemplate] = field(default_factory=dict)
    responses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    response_statuses: list[tuple[str, int]] = field(default_factory=list)

    def add_response(self, endpoint: str, payload: dict[str, Any]) -> None:
        self.responses.setdefault(endpoint, []).append(payload)


class BrowserShopScanner:
    def __init__(
        self,
        *,
        profile_dir: Path,
        storage_state_path: Path,
        executable_path: Optional[Path],
        headless: bool,
        timeout: float,
        page_wait: float,
        manual_challenge_seconds: int,
        max_pages: int,
        page_size: int,
        fetch_mode: str,
        request_interval: float,
        logger: logging.Logger,
    ):
        self.profile_dir = profile_dir
        self.storage_state_path = storage_state_path
        self.executable_path = executable_path
        self.headless = headless
        self.timeout_ms = int(max(5, timeout) * 1000)
        self.page_wait_ms = int(max(0, page_wait) * 1000)
        self.manual_challenge_seconds = max(0, manual_challenge_seconds)
        self.max_pages = max(1, max_pages)
        self.page_size = min(max(1, page_size), 100)
        self.fetch_mode = fetch_mode
        self.rate_limiter = GlobalRateLimiter(request_interval)
        self.logger = logger
        self._pw: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self) -> "BrowserShopScanner":
        profile_was_empty = not self.profile_dir.exists() or not any(self.profile_dir.iterdir())
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            executable_path=str(self.executable_path) if self.executable_path else None,
            headless=self.headless,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1365, "height": 900},
            java_script_enabled=True,
            accept_downloads=False,
        )
        self.context.set_default_timeout(self.timeout_ms)
        self.context.set_default_navigation_timeout(self.timeout_ms)
        if profile_was_empty:
            self._restore_storage_state_backup()
        return self

    def _restore_storage_state_backup(self) -> None:
        if not self.context or not self.storage_state_path.exists():
            return
        try:
            state = json.loads(self.storage_state_path.read_text("utf-8"))
            cookies = state.get("cookies") if isinstance(state, dict) else None
            if isinstance(cookies, list) and cookies:
                self.context.add_cookies(cookies)
            origins = state.get("origins") if isinstance(state, dict) else None
            mapping: dict[str, list[dict[str, str]]] = {}
            if isinstance(origins, list):
                for item in origins:
                    if isinstance(item, dict) and isinstance(item.get("origin"), str) and isinstance(item.get("localStorage"), list):
                        mapping[item["origin"]] = [x for x in item["localStorage"] if isinstance(x, dict)]
            if mapping:
                encoded = json.dumps(mapping, ensure_ascii=False)
                self.context.add_init_script(
                    script=(
                        "(() => { const map = " + encoded + "; "
                        "const rows = map[location.origin] || []; "
                        "for (const row of rows) { try { localStorage.setItem(row.name, row.value); } catch (_) {} } })();"
                    )
                )
            self.logger.info("已从 browser_state.json 恢复浏览器会话备份。")
        except Exception as exc:
            self.logger.warning("恢复 browser_state.json 失败，将继续使用浏览器目录：%s", exc)

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.save_state()
        finally:
            if self.context:
                self.context.close()
            if self._pw:
                self._pw.stop()

    def save_state(self) -> None:
        if not self.context:
            return
        try:
            self.context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            self.logger.debug("保存 storage state 失败：%s", exc)

    @staticmethod
    def _endpoint_name(url: str) -> str:
        path = urllib.parse.urlparse(url).path
        lower = path.casefold()
        if "goodslist" in lower or re.search(r"/(?:goods|products?)/(?:list|search)$", lower):
            return GOODS_ENDPOINT
        if "categorylist" in lower or re.search(r"/categor(?:y|ies)/(?:list|all)$", lower):
            return CATEGORY_ENDPOINT
        if lower.endswith("/shop/info") or lower.endswith("/shopapi/shop/info") or re.search(r"/shop/(?:detail|info)$", lower):
            return INFO_ENDPOINT
        return ""

    def _new_page_with_capture(self) -> tuple[Page, CaptureState]:
        assert self.context is not None
        page = self.context.new_page()
        capture = CaptureState()

        def on_request(request: Request) -> None:
            endpoint = self._endpoint_name(request.url)
            if not endpoint or request.method.upper() != "POST":
                return
            try:
                payload = request.post_data_json if isinstance(request.post_data_json, dict) else {}
            except Exception:
                try:
                    payload = json.loads(request.post_data or "{}")
                except (TypeError, json.JSONDecodeError):
                    payload = {}
            try:
                headers = request.all_headers()
            except Exception:
                headers = request.headers
            capture.templates[endpoint] = RequestTemplate(request.url, payload, dict(headers))

        def on_response(response: Response) -> None:
            endpoint = self._endpoint_name(response.url)
            if not endpoint:
                return
            capture.response_statuses.append((endpoint, response.status))
            try:
                payload = response.json()
            except Exception:
                return
            if isinstance(payload, dict):
                capture.add_response(endpoint, payload)

        page.on("request", on_request)
        page.on("response", on_response)
        return page, capture

    def scan_shop(self, candidate: Any, keywords: Sequence[str]) -> ShopScanResult:
        token = candidate["token"]
        shop_url = normalize_shop_url(candidate["url"]) or candidate["url"]
        page, capture = self._new_page_with_capture()
        challenge_seen = False
        try:
            self.rate_limiter.wait()
            try:
                nav_response = page.goto(shop_url, wait_until="domcontentloaded")
            except PlaywrightTimeoutError as exc:
                raise BrowserScanError(f"页面打开超时：{exc}", "network_error") from exc
            except Exception as exc:
                raise BrowserScanError(f"页面打开失败：{exc}", "network_error") from exc

            nav_status = nav_response.status if nav_response else None
            if nav_status == 429:
                raise BrowserScanError("页面返回 HTTP 429", "rate_limited", 429)

            if self.page_wait_ms:
                page.wait_for_timeout(self.page_wait_ms)

            if nav_status == 403 or self._is_challenge(page):
                challenge_seen = True
                solved = self._wait_for_manual_challenge(page, shop_url)
                if not solved:
                    status = "challenge_required" if self._is_challenge(page) else "blocked"
                    raise BrowserScanError(
                        "检测到验证/阻断页面。请使用有头模式运行并在浏览器中正常完成验证。",
                        status,
                        nav_status or 403,
                    )
                self.save_state()
                page.wait_for_timeout(1200)

            info_payload = self._latest_valid(capture.responses.get(INFO_ENDPOINT, []))
            if not info_payload:
                info_payload = self._fetch_api(
                    page,
                    capture,
                    INFO_ENDPOINT,
                    {"token": token, "category_key": ""},
                )

            info = self._extract_data_dict(info_payload)
            page_text = self._body_text(page)
            shop_name = clean_text(
                info.get("nickname")
                or info.get("shop_name")
                or info.get("name")
                or self._page_title(page)
                or token
            )
            canonical_url = normalize_shop_url(info.get("link") or page.url) or shop_url
            api_host = urllib.parse.urlparse(page.url or shop_url).hostname or ""
            closed = bool(CLOSED_RE.search(page_text + " " + json.dumps(info, ensure_ascii=False)))

            initial_payloads = capture.responses.get(GOODS_ENDPOINT, [])
            products: list[dict[str, Any]] = []
            partial_error = ""
            for payload in initial_payloads:
                products.extend(self._extract_items(payload))

            try:
                if self.fetch_mode == "keyword":
                    for keyword in keywords:
                        products.extend(self._fetch_goods_pages(page, capture, token, keyword, 0))
                else:
                    products.extend(self._fetch_goods_pages(page, capture, token, "", 0))
                    if not products:
                        category_payload = self._latest_valid(capture.responses.get(CATEGORY_ENDPOINT, []))
                        if not category_payload:
                            category_payload = self._fetch_api(
                                page,
                                capture,
                                CATEGORY_ENDPOINT,
                                {"token": token, "goods_type": "card", "category_key": ""},
                            )
                        for category_id in self._extract_category_ids(category_payload):
                            products.extend(self._fetch_goods_pages(page, capture, token, "", category_id))
            except BrowserScanError as exc:
                if products:
                    partial_error = str(exc)
                else:
                    raise

            products.extend(self._dom_products(page))
            products = self._dedupe_products(products)
            matches = self._build_matches(products, keywords, page.url, closed)

            if closed:
                status = "closed"
            elif partial_error:
                status = "partial_success"
            elif not products:
                status = "empty_shop"
            elif not matches:
                status = "no_match"
            else:
                status = "success"

            self.save_state()
            return ShopScanResult(
                token=token,
                status=status,
                shop_name=shop_name,
                shop_url=canonical_url,
                api_host=api_host,
                scanned_item_count=len(products),
                matches=matches,
                error=partial_error,
                challenge_seen=challenge_seen,
                http_status=nav_status,
                engine="browser",
            )
        except BrowserScanError as exc:
            return ShopScanResult(
                token=token,
                status=exc.status,
                shop_url=shop_url,
                error=str(exc),
                challenge_seen=challenge_seen,
                http_status=exc.http_status,
                engine="browser",
            )
        except Exception as exc:
            return ShopScanResult(
                token=token,
                status="failed",
                shop_url=shop_url,
                error=f"未处理异常：{type(exc).__name__}: {exc}",
                challenge_seen=challenge_seen,
                engine="browser",
            )
        finally:
            page.close()

    def _wait_for_manual_challenge(self, page: Page, shop_url: str) -> bool:
        if self.headless or self.manual_challenge_seconds <= 0:
            return False
        self.logger.warning(
            "浏览器出现验证页。请在打开的 Chromium 窗口中正常完成验证；程序最多等待 %s 秒。",
            self.manual_challenge_seconds,
        )
        deadline = time.monotonic() + self.manual_challenge_seconds
        last_reload = 0.0
        while time.monotonic() < deadline:
            page.wait_for_timeout(1000)
            if not self._is_challenge(page):
                if "/shop/" not in page.url:
                    try:
                        page.goto(shop_url, wait_until="domcontentloaded")
                        page.wait_for_timeout(1200)
                    except Exception:
                        pass
                if not self._is_challenge(page):
                    self.logger.info("验证已完成，继续扫描。")
                    return True
            # Some verification pages only set a cookie and do not navigate back.
            if time.monotonic() - last_reload > 20:
                last_reload = time.monotonic()
                try:
                    page.goto(shop_url, wait_until="domcontentloaded")
                except Exception:
                    pass
        return False

    def _is_challenge(self, page: Page) -> bool:
        text = " ".join([self._page_title(page), self._body_text(page)[:8000]])
        if CHALLENGE_RE.search(text):
            return True
        try:
            return bool(page.locator("iframe[src*='captcha'], [class*='captcha'], [id*='captcha']").count())
        except Exception:
            return False

    @staticmethod
    def _page_title(page: Page) -> str:
        try:
            return clean_text(page.title())
        except Exception:
            return ""

    @staticmethod
    def _body_text(page: Page) -> str:
        try:
            return clean_text(page.locator("body").inner_text(timeout=3000))
        except Exception:
            return ""

    def _fetch_api(
        self,
        page: Page,
        capture: CaptureState,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        template = capture.templates.get(endpoint)
        url = template.url if template else urllib.parse.urljoin(page.url, endpoint)
        headers = self._safe_replay_headers(template.headers if template else {})
        merged_payload = dict(template.payload) if template else {}
        merged_payload.update(payload)
        self.rate_limiter.wait()
        try:
            result = page.evaluate(
                """
                async ({url, payload, headers, timeoutMs}) => {
                  const controller = new AbortController();
                  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
                  try {
                    const response = await fetch(url, {
                      method: 'POST',
                      credentials: 'include',
                      headers: {'content-type': 'application/json', 'accept': 'application/json, text/plain, */*', ...headers},
                      body: JSON.stringify(payload),
                      signal: controller.signal
                    });
                    return {status: response.status, text: await response.text()};
                  } catch (error) {
                    return {status: 0, error: String(error), text: ''};
                  } finally {
                    clearTimeout(timeoutId);
                  }
                }
                """,
                {"url": url, "payload": merged_payload, "headers": headers, "timeoutMs": self.timeout_ms},
            )
        except Exception as exc:
            raise BrowserScanError(f"浏览器 API 调用失败：{endpoint}: {exc}", "network_error") from exc

        status = safe_int(result.get("status")) or 0
        if status == 429:
            raise BrowserScanError(f"{endpoint} HTTP 429", "rate_limited", 429)
        if status == 403:
            status_name = "challenge_required" if self._is_challenge(page) else "blocked"
            raise BrowserScanError(f"{endpoint} HTTP 403", status_name, 403)
        if status == 404:
            raise BrowserScanError(f"{endpoint} HTTP 404，接口可能已变更", "api_changed", 404)
        if status <= 0 or status >= 500:
            raise BrowserScanError(
                f"{endpoint} HTTP {status or 'network error'} {clean_text(result.get('error'))}",
                "network_error",
                status or None,
            )
        if status != 200:
            raise BrowserScanError(f"{endpoint} HTTP {status}", "failed", status)
        try:
            parsed = json.loads(result.get("text") or "")
        except json.JSONDecodeError as exc:
            text = clean_text(result.get("text"))[:300]
            if CHALLENGE_RE.search(text):
                challenge_status = "rate_limited" if JAVASCRIPT_CHALLENGE_RE.search(text) else "challenge_required"
                raise BrowserScanError(f"{endpoint} 返回验证页面", challenge_status, status) from exc
            raise BrowserScanError(f"{endpoint} 返回非 JSON：{text}", "parse_error", status) from exc
        if not isinstance(parsed, dict):
            raise BrowserScanError(f"{endpoint} JSON 结构异常", "parse_error", status)
        return parsed

    @staticmethod
    def _safe_replay_headers(headers: dict[str, str]) -> dict[str, str]:
        blocked = {
            "host", "content-length", "cookie", "origin", "referer", "user-agent",
            "connection", "accept-encoding", "content-type", "accept",
        }
        result: dict[str, str] = {}
        for key, value in headers.items():
            lower = key.lower()
            if lower in blocked or lower.startswith("sec-") or lower.startswith(":"):
                continue
            # Preserve visitor/device and application-specific headers observed from the real page.
            if lower in {"visitorid", "authorization"} or lower.startswith(("x-", "app-", "device-")):
                result[key] = value
        return result

    def _fetch_goods_pages(
        self,
        page: Page,
        capture: CaptureState,
        token: str,
        keyword: str,
        category_id: int,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen_pages: set[tuple[str, ...]] = set()
        total: Optional[int] = None
        for current in range(1, self.max_pages + 1):
            payload = self._fetch_api(
                page,
                capture,
                GOODS_ENDPOINT,
                {
                    "token": token,
                    "keywords": keyword,
                    "category_id": category_id,
                    "goods_type": "card",
                    "current": current,
                    "pageSize": self.page_size,
                },
            )
            page_items = self._extract_items(payload)
            if total is None:
                total = self._extract_total(payload)
            if not page_items:
                break
            signature = tuple(
                clean_text(x.get("goods_key") or x.get("id") or x.get("link") or x.get("name"))
                for x in page_items
            )
            if signature in seen_pages:
                break
            seen_pages.add(signature)
            items.extend(page_items)
            if total is not None and len(self._dedupe_products(items)) >= total:
                break
        return items

    @staticmethod
    def _latest_valid(payloads: Sequence[dict[str, Any]]) -> dict[str, Any]:
        for payload in reversed(payloads):
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _extract_data_dict(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            for key in ("shop", "info", "detail"):
                if isinstance(data.get(key), dict):
                    return data[key]
            return data
        return {}

    @classmethod
    def _extract_items(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        candidates: list[Any] = [payload]
        if isinstance(payload.get("data"), (dict, list)):
            candidates.append(payload["data"])
        for node in candidates:
            if isinstance(node, list):
                return [x for x in node if isinstance(x, dict)]
            if not isinstance(node, dict):
                continue
            for key in ("list", "records", "rows", "items", "goods", "products", "data"):
                value = node.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
                if isinstance(value, dict):
                    nested = cls._extract_items(value)
                    if nested:
                        return nested
        return []

    @classmethod
    def _extract_total(cls, payload: dict[str, Any]) -> Optional[int]:
        if not isinstance(payload, dict):
            return None
        for key in ("total", "total_count", "count"):
            value = safe_int(payload.get(key))
            if value is not None:
                return value
        data = payload.get("data")
        if isinstance(data, dict):
            return cls._extract_total(data)
        return None

    @classmethod
    def _extract_category_ids(cls, payload: dict[str, Any]) -> list[int]:
        rows = cls._extract_items(payload)
        result: list[int] = []
        for row in rows:
            category_id = safe_int(row.get("id") or row.get("category_id"))
            count = safe_int(row.get("goods_count") or row.get("count"))
            if category_id and (count is None or count > 0):
                result.append(category_id)
        return list(dict.fromkeys(result))

    @staticmethod
    def _dom_products(page: Page) -> list[dict[str, Any]]:
        try:
            rows = page.evaluate(
                r"""
                () => Array.from(document.querySelectorAll('a[href*="/item/"]')).map(a => {
                  const box = a.closest('article,li,[class*="goods"],[class*="product"],[class*="item"],div') || a;
                  const text = (box.innerText || a.innerText || a.textContent || '').trim();
                  const lines = text.split(/\n+/).map(x => x.trim()).filter(Boolean);
                  const name = (a.getAttribute('title') || lines.find(x => !/^[¥￥]?\s*\d+(?:\.\d+)?$/.test(x)) || '').trim();
                  return {name, link: a.href, _dom_text: text};
                }).filter(x => x.name && x.link)
                """
            )
            return [x for x in rows if isinstance(x, dict)]
        except Exception:
            return []

    @staticmethod
    def _dedupe_products(products: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in products:
            if not isinstance(item, dict):
                continue
            key = clean_text(item.get("goods_key") or item.get("id") or item.get("link") or item.get("name"))
            if not key:
                continue
            previous = result.get(key)
            if previous:
                merged = dict(previous)
                merged.update({k: v for k, v in item.items() if v not in (None, "", [], {})})
                result[key] = merged
            else:
                result[key] = item
        return list(result.values())

    def _build_matches(
        self,
        products: Sequence[dict[str, Any]],
        keywords: Sequence[str],
        base_url: str,
        shop_closed: bool,
    ) -> list[ProductMatch]:
        matches: list[ProductMatch] = []
        normalized_keywords = merge_unique(keywords)
        for item in products:
            title = clean_text(item.get("name") or item.get("title") or item.get("goods_name"))
            if not title:
                continue
            category_obj = item.get("category") if isinstance(item.get("category"), dict) else {}
            category_name = clean_text(
                category_obj.get("name") or item.get("category_name") or item.get("cate_name")
            )
            identity = " ".join([title, category_name])
            if not has_target_brand(title, category_name):
                continue
            normalized_identity = normalize_identity(identity)
            hit = [kw for kw in normalized_keywords if normalize_identity(kw) in normalized_identity]
            if not hit:
                continue

            extend = item.get("extend") if isinstance(item.get("extend"), dict) else {}
            listed_price = safe_float(
                item.get("price")
                if item.get("price") is not None
                else item.get("sale_price")
                if item.get("sale_price") is not None
                else item.get("real_price")
            )
            real_price = safe_float(item.get("real_price") or item.get("origin_price"))
            stock = safe_int(
                extend.get("stock_count")
                if extend.get("stock_count") is not None
                else item.get("stock_count")
                if item.get("stock_count") is not None
                else item.get("stock")
            )
            status_num = safe_int(item.get("status"))
            if shop_closed:
                product_status = "店铺暂停营业"
            elif status_num is not None and status_num != 1:
                product_status = "下架/不可用"
            elif stock == 0:
                product_status = "缺货"
            elif stock is None:
                product_status = "库存未知"
            else:
                product_status = "有货"

            product_key = clean_text(item.get("goods_key") or item.get("id"))
            product_url = clean_text(item.get("link") or item.get("url"))
            if product_url.startswith("/"):
                product_url = urllib.parse.urljoin(base_url, product_url)
            if not product_url and product_key:
                product_url = urllib.parse.urljoin(base_url, f"/item/{urllib.parse.quote(product_key, safe='._~-')}")
            product_url = safe_http_url(product_url)

            send_order = safe_int(extend.get("send_order") if extend else item.get("send_order"))
            auto_delivery = "是" if send_order == 0 else "否" if send_order is not None else "未知"
            matches.append(
                ProductMatch(
                    product_key=product_key,
                    product_name=title,
                    matched_keywords=hit,
                    listed_price=listed_price,
                    real_price=real_price,
                    stock_count=stock,
                    product_status=product_status,
                    category_name=category_name,
                    product_url=product_url,
                    auto_delivery=auto_delivery,
                    goods_type=clean_text(item.get("goods_type") or item.get("type")),
                    raw=item,
                )
            )
        return matches
