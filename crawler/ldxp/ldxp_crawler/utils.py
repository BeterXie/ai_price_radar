from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

ALLOWED_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"}
PRICE_RE = re.compile(r"(?:[¥￥]\s*)?(\d+(?:\.\d{1,2})?)")
SHOP_PATH_RE = re.compile(r"/shop/([^/?#]+)", re.I)
SHOP_URL_RE = re.compile(
    r"(?:(?:https?:)?//)?(?:pay\.|www\.)?ldxp\.cn/shop/[A-Za-z0-9._~-]+",
    re.I,
)
CLOSED_RE = re.compile(r"店铺已打烊|店铺打烊|已打烊|暂停营业|停止营业|暂不营业|closed", re.I)
CHALLENGE_RE = re.compile(
    r"verification|captcha|challenge|人机验证|安全验证|滑块验证|请完成验证|访问验证|阿里云验证码|var\s+arg1\s*=",
    re.I,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    return re.sub(r"\s+", " ", text).strip()


def merge_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = clean_text(item)
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        match = PRICE_RE.search(str(value))
        return float(match.group(1)) if match else None


def safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def normalize_input_url(value: str) -> str:
    value = html.unescape(value.strip()).replace("\\/", "/")
    value = value.replace("\\u002F", "/").replace("\\u003A", ":")
    if value.startswith("//"):
        return "https:" + value
    if re.match(r"^(?:pay\.|www\.)?ldxp\.cn/", value, re.I):
        return "https://" + value
    return value


def extract_shop_token(value: str) -> Optional[str]:
    try:
        value = normalize_input_url(value)
        parsed = urllib.parse.urlparse(value)
        match = SHOP_PATH_RE.search(parsed.path)
        if not match:
            return None
        token = urllib.parse.unquote(match.group(1)).strip()
        if not token or len(token) > 128:
            return None
        if not re.fullmatch(r"[A-Za-z0-9._~-]+", token):
            return None
        return token
    except Exception:
        return None


def normalize_shop_url(value: str, preferred_host: str = "pay.ldxp.cn") -> Optional[str]:
    value = normalize_input_url(value)
    token = extract_shop_token(value)
    if not token:
        return None
    try:
        host = (urllib.parse.urlparse(value).hostname or preferred_host).lower()
    except Exception:
        host = preferred_host
    if host not in ALLOWED_HOSTS:
        host = preferred_host
    return f"https://{host}/shop/{urllib.parse.quote(token, safe='._~-')}"


def extract_shop_urls(text: str) -> list[str]:
    if not text:
        return []
    variants = [text, html.unescape(text), urllib.parse.unquote(text), urllib.parse.unquote_plus(text)]
    found: list[str] = []
    for variant in variants:
        variant = variant.replace("\\/", "/").replace("\\u002F", "/").replace("\\u003A", ":")
        for match in SHOP_URL_RE.finditer(variant):
            url = normalize_shop_url(match.group(0))
            if url:
                found.append(url)
    return merge_unique(found)


def json_loads_or(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def safe_excel_text(value: Any) -> str:
    text = clean_text(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def safe_http_url(value: Any) -> str:
    url = clean_text(value)
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class GlobalRateLimiter:
    """Thread-safe process-wide minimum request spacing."""

    def __init__(self, min_interval: float):
        self.min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._last_at = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            remaining = self.min_interval - (now - self._last_at)
            if remaining > 0:
                time.sleep(remaining)
            self._last_at = time.monotonic()
