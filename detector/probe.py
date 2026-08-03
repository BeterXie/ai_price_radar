from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

from price_radar_http import PinnedHTTPSClient, PinnedResponse as ProbeResponse


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TASK_BYTES = 2 * 1024 * 1024
MAX_TASK_SECONDS = 15.0
LDXP_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"}
LDXP_PATH = re.compile(r"/shop/([A-Za-z0-9._~-]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    detected_platform: str
    source_url: str
    source_key: str
    shop_name: str = ""
    product_count: int = 0

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
        source_url = f"https://pay.ldxp.cn/shop/{urllib.parse.quote(token, safe='._~-')}"
        return ProbeResult("ldxp", source_url, token.casefold())

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
    token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return ProbeResult("other", normalized, normalized, host, 0)
