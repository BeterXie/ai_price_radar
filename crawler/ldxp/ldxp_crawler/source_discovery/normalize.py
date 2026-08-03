from __future__ import annotations

import hashlib
import urllib.parse

from price_radar_http import PinnedHTTPSClient


ORIGIN_KEY_PLATFORMS = frozenset({"dujiao_next", "woocommerce", "ldxp"})


def normalize_candidate_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise ValueError("candidate URL contains invalid control characters")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.fragment:
        raise ValueError("candidate URL must not contain a fragment")
    if parsed.scheme.casefold() == "http":
        raw = urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    elif parsed.scheme and parsed.scheme.casefold() != "https":
        raise ValueError("candidate URL must use HTTPS")
    return PinnedHTTPSClient.normalize_url(raw)


def normalize_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    host = parsed.hostname or ""
    rendered_host = f"[{host}]" if ":" in host else host
    return urllib.parse.urlunsplit(("https", rendered_host, "", "", ""))


def candidate_key_for(normalized_url: str, platform_hint: str) -> str:
    hint = str(platform_hint or "").strip().casefold().replace("-", "_")
    if hint in ORIGIN_KEY_PLATFORMS:
        return normalize_origin(normalized_url)
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
