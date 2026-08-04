from __future__ import annotations

from typing import Any


BLOCKED_HEADERS = frozenset({
    "authorization",
    "cookie",
    "proxy-authorization",
    "visitorid",
    "x-api-key",
    "x-auth-token",
})

BLOCKED_PREFIXES = ("device-", "app-", "sec-", "x-")


def is_blocked_header(name: str) -> bool:
    lower = str(name or "").strip().casefold()
    if not lower:
        return True
    if lower in BLOCKED_HEADERS:
        return True
    return any(lower.startswith(prefix) for prefix in BLOCKED_PREFIXES)


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    """Keep only neutral, non-sensitive request headers for any public request."""
    result: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if is_blocked_header(str(key)):
            continue
        text = str(value)
        if "\r" in text or "\n" in text:
            continue
        result[str(key)] = text
    return result


def assert_no_blocked_headers(headers: dict[str, Any] | None) -> None:
    """Raise if a request construction path would leak a sensitive header."""
    for key in (headers or {}):
        if is_blocked_header(str(key)):
            raise ValueError(f"blocked header must not be used: {key}")
