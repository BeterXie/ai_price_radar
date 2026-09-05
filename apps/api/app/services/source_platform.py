from __future__ import annotations

import hashlib
import ipaddress
import re
import urllib.parse
from dataclasses import dataclass


SOURCE_PLATFORM_LABELS = {
    "ldxp": "链动小铺",
    "dujiao_next": "Dujiao-Next",
    "merchant_json": "商家 Feed",
    "woocommerce": "WooCommerce",
    "16688": "16688",
    "schema_org": "独立站",
    "other": "其他独立站",
}

SOURCE_KIND_BY_PLATFORM = {
    "ldxp": "public_page",
    "dujiao_next": "public_api",
    "merchant_json": "public_feed",
    "woocommerce": "public_api",
    "16688": "public_api",
    "schema_org": "structured_data",
    "other": "public_page",
}

SOURCE_KIND_LABELS = {
    "public_page": "公开页面",
    "public_api": "公开 API",
    "public_feed": "公开 Feed",
    "structured_data": "结构化数据",
}

PLATFORM_ALIASES = {
    "merchant_feed": "merchant_json",
}

DISABLED_SOURCE_PLATFORMS: set[str] = {
    "dujiao_next",
}


def get_disabled_source_platforms() -> set[str]:
    return set(DISABLED_SOURCE_PLATFORMS)


def is_source_platform_disabled(value: str) -> bool:
    return canonical_source_platform(value) in DISABLED_SOURCE_PLATFORMS

LDXP_HOSTS = {"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn", "wzyp.cn", "www.wzyp.cn"}
PLATFORM_16688_HOSTS = {"16688.com.cn", "www.16688.com.cn"}
PLATFORM_16688_PATH = re.compile(r"^/shop/([A-Za-z0-9._~-]+)$", re.IGNORECASE)


def canonical_source_platform(value: str) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    return PLATFORM_ALIASES.get(normalized, normalized)


def source_platform_label(value: str) -> str:
    platform = canonical_source_platform(value)
    return SOURCE_PLATFORM_LABELS.get(platform, SOURCE_PLATFORM_LABELS["other"])


def source_kind(value: str) -> str:
    return SOURCE_KIND_BY_PLATFORM.get(canonical_source_platform(value), "public_page")


def source_kind_label(value: str) -> str:
    return SOURCE_KIND_LABELS.get(value, value)


def workflow_status(value: str) -> str:
    return {
        "queued": "approved",
        "validating": "detecting",
        "validated": "approved",
        "onboarded": "published",
        "no_products": "validation_failed",
    }.get(value, value)


@dataclass(frozen=True, slots=True)
class SourceDetection:
    platform: str
    source_url: str
    source_key: str
    shop_token: str


FORBIDDEN_HOSTS = {"localhost", "0.0.0.0", "127.0.0.1", "::1"}
FORBIDDEN_HOST_SUFFIXES = (
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".intranet",
    ".priv",
    ".arpa",
)


def normalize_public_https_url(value: object) -> str:
    """Normalize a URL without DNS resolution or outbound network access."""
    url_str = str(value or "").strip()
    if any(ch in url_str for ch in ("\r", "\n", "\t", "\0", " ")):
        raise ValueError("来源地址包含非法控制字符或空格")
    parsed = urllib.parse.urlsplit(url_str)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or parsed.username or parsed.password:
        raise ValueError("来源地址必须是公开 HTTPS URL")
    if host in FORBIDDEN_HOSTS or host.endswith(FORBIDDEN_HOST_SUFFIXES):
        raise ValueError("来源地址不能指向本地或内部主机")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if not literal_ip.is_global or literal_ip.is_loopback or literal_ip.is_private or literal_ip.is_link_local:
            raise ValueError("来源地址不能使用私有或保留 IP")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("来源地址端口无效") from exc
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = f"{rendered_host}:{port}" if port and port != 443 else rendered_host
    return urllib.parse.urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))

def _ldxp_detection(url: str) -> SourceDetection | None:
    parsed = urllib.parse.urlsplit(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.rstrip("/").split("/") if part]
    if (parsed.hostname or "").casefold() not in LDXP_HOSTS or len(parts) != 2 or parts[0].casefold() != "shop":
        return None
    token = parts[1].strip()
    if not token or len(token) > 128 or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-" for character in token):
        return None
    host = (parsed.hostname or "").casefold()
    canonical_host = "wzyp.cn" if host in {"wzyp.cn", "www.wzyp.cn"} else "pay.ldxp.cn"
    source_url = f"https://{canonical_host}/shop/{urllib.parse.quote(token, safe='._~-')}"
    return SourceDetection("ldxp", source_url, token.casefold(), token)


def _16688_detection(url: str) -> SourceDetection | None:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold()
    match = PLATFORM_16688_PATH.fullmatch(parsed.path.rstrip("/"))
    if (
        host not in PLATFORM_16688_HOSTS
        or match is None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        return None
    shop_no = urllib.parse.unquote(match.group(1)).strip()
    source_url = f"https://{host}/shop/{urllib.parse.quote(shop_no, safe='._~-')}"
    return SourceDetection("16688", source_url, source_url, f"16688-{shop_no}")


def prepare_source_submission(value: object) -> SourceDetection:
    """Normalize a submission without DNS resolution or outbound network access."""
    normalized = normalize_public_https_url(value)
    if ldxp := _ldxp_detection(normalized):
        return SourceDetection("unknown", ldxp.source_url, ldxp.source_key, ldxp.shop_token)
    if platform := _16688_detection(normalized):
        return SourceDetection("unknown", platform.source_url, platform.source_key, platform.shop_token)
    token = "source-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return SourceDetection("unknown", normalized, normalized, token)
