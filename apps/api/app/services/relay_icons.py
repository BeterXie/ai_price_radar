"""Discover small raster favicons from approved relay homepages, with bounded caching."""
from __future__ import annotations

import base64
import binascii
import http.client
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from price_radar_http import PinnedHTTPSClient

_MAX_BYTES = 256 * 1024
_MAX_DATA_URI_LENGTH = ((_MAX_BYTES + 2) // 3) * 4 + 80
_MAX_CACHE_ENTRIES = 128
_POSITIVE_TTL = 24 * 60 * 60
_NEGATIVE_TTL = 30
_FETCH_SECONDS = 16
_SLOT_WAIT_SECONDS = 8
_FETCH_ERRORS = (OSError, ValueError, http.client.HTTPException)


class RelayIconBusy(Exception):
    """Transient capacity exhaustion, distinct from a missing site icon."""


@dataclass(frozen=True)
class RelayIcon:
    body: bytes
    media_type: str


class _IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[int, str]] = []
        self.base_href: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "base" and self.base_href is None:
            href = dict(attrs).get("href")
            if href is not None and len(href) <= 2048:
                self.base_href = href
            return
        if tag != "link" or len(self.links) >= 8:
            return
        values = dict(attrs)
        rel = (values.get("rel") or "").casefold().split()
        href = values.get("href") or ""
        max_length = _MAX_DATA_URI_LENGTH if href.startswith("data:image/") else 2048
        if not href or len(href) > max_length or "svg" in (values.get("type") or "").casefold():
            return
        if "icon" in rel:
            self.links.append((0, href))
        elif "apple-touch-icon" in rel:
            self.links.append((1, href))


def _raster_icon(body: bytes) -> RelayIcon | None:
    # Never serve remote SVG/HTML from our origin. Browser decoding supplies the
    # final validity check; a malformed raster falls back to the station initial.
    media_type = ""
    if len(body) >= 24 and body.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif len(body) >= 6 and body[:4] == b"\x00\x00\x01\x00":
        media_type = "image/x-icon"
    elif len(body) >= 10 and body[:6] in (b"GIF87a", b"GIF89a"):
        media_type = "image/gif"
    elif len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        media_type = "image/webp"
    elif len(body) >= 4 and body.startswith(b"\xff\xd8\xff") and body.endswith(b"\xff\xd9"):
        media_type = "image/jpeg"
    return RelayIcon(body, media_type) if media_type else None


def _fetch_icon(home: str) -> RelayIcon | None:
    client = PinnedHTTPSClient(
        # Inline favicons can make the HTML larger than the image itself.
        max_response_bytes=1024 * 1024,
        max_task_bytes=2 * 1024 * 1024,
        max_task_seconds=_FETCH_SECONDS,
        request_timeout=5,
        user_agent="AI-Price-Memory-SiteIcon/1",
    )
    links: list[str] = []
    resource_base = home
    try:
        page = client.get(home, accept="text/html")
        if page.status == 200 and page.headers.get("content-type", "").split(";", 1)[0].strip().lower() in {"text/html", "application/xhtml+xml"}:
            parser = _IconLinks()
            try:
                parser.feed(page.body.decode("utf-8", errors="replace"))
            except AssertionError:
                # HTMLParser rejects malformed declarations such as <![bogus]>.
                # Ignore the incomplete document and still try /favicon.ico.
                parser = _IconLinks()
            if parser.base_href is not None:
                resource_base = urljoin(home, parser.base_href)
            links = [href for _, href in sorted(parser.links, key=lambda item: item[0])]
    except _FETCH_ERRORS:
        pass
    candidates: list[str] = []
    for href in links:
        if href.startswith("data:"):
            icon = _inline_icon(href)
            if icon:
                return icon
            continue
        try:
            candidate = PinnedHTTPSClient.normalize_url(urljoin(resource_base, href))
        except (ValueError, UnicodeError):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
        if len(candidates) == 2:
            break
    fallback = urljoin(home, "/favicon.ico")
    if fallback not in candidates:
        candidates.append(fallback)
    for candidate in candidates:
        try:
            response = client.get(candidate, accept="image/png,image/x-icon,image/webp,image/jpeg,image/gif")
            if response.status == 200 and len(response.body) <= _MAX_BYTES:
                icon = _raster_icon(response.body)
                if icon:
                    return icon
        except _FETCH_ERRORS:
            continue
    return None


def _inline_icon(value: str) -> RelayIcon | None:
    header, separator, data = value.partition(",")
    if not separator or len(value) > _MAX_DATA_URI_LENGTH or header.lower() not in {
        "data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64",
        "data:image/gif;base64", "data:image/x-icon;base64", "data:image/vnd.microsoft.icon;base64",
    }:
        return None
    try:
        body = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error):
        return None
    return _raster_icon(body) if len(body) <= _MAX_BYTES else None


def _homepage(website_url: str) -> str:
    normalized = urlsplit(PinnedHTTPSClient.normalize_url(website_url))
    return urlunsplit((normalized.scheme, normalized.netloc, "/", "", ""))


def read_icon_cache(website_url: str, cache: dict) -> tuple[RelayIcon | None, bool]:
    """A previous success remains usable during upstream outages and restarts."""
    if not isinstance(cache, dict):
        return None, False
    try:
        if cache.get("home") != _homepage(website_url):
            return None, False
        data = cache.get("body")
        if not isinstance(data, str) or len(data) > _MAX_DATA_URI_LENGTH:
            return None, False
        body = base64.b64decode(data, validate=True)
        icon = _raster_icon(body) if len(body) <= _MAX_BYTES else None
        synced_at = datetime.fromisoformat(cache["synced_at"])
        age = (datetime.now(timezone.utc) - synced_at).total_seconds()
        return icon, icon is not None and 0 <= age < _POSITIVE_TTL
    except (ValueError, TypeError, KeyError, binascii.Error):
        return None, False


def make_icon_cache(website_url: str, icon: RelayIcon) -> dict:
    return {"home": _homepage(website_url), "body": base64.b64encode(icon.body).decode("ascii"), "synced_at": datetime.now(timezone.utc).isoformat()}


_cache: OrderedDict[str, tuple[float, RelayIcon | None]] = OrderedDict()
_lock = threading.Lock()
_in_flight: dict[str, threading.Event] = {}
_slots = threading.BoundedSemaphore(4)


def get_relay_icon(website_url: str) -> RelayIcon | None:
    try:
        # Strip invitation paths and query parameters; only the public homepage
        # declares site identity. The probe endpoint and credentials are unused.
        home = _homepage(website_url)
    except (ValueError, UnicodeError):
        return None
    with _lock:
        cached = _cache.get(home)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(home)
            return cached[1]
        pending = _in_flight.get(home)
        if pending is None:
            pending = threading.Event()
            _in_flight[home] = pending
            owns_fetch = True
        else:
            owns_fetch = False
    if not owns_fetch:
        # The owner may first queue for a slot, then use the full fetch budget.
        if pending.wait(timeout=_SLOT_WAIT_SECONDS + _FETCH_SECONDS + 1):
            with _lock:
                cached = _cache.get(home)
                if cached and cached[0] > time.monotonic():
                    return cached[1]
        raise RelayIconBusy()
    acquired = False
    try:
        acquired = _slots.acquire(timeout=_SLOT_WAIT_SECONDS)
        if not acquired:
            raise RelayIconBusy()
        try:
            icon = _fetch_icon(home)
        except _FETCH_ERRORS:
            icon = None
        with _lock:
            _cache[home] = (time.monotonic() + (_POSITIVE_TTL if icon else _NEGATIVE_TTL), icon)
            _cache.move_to_end(home)
            while len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        return icon
    finally:
        with _lock:
            _in_flight.pop(home, None)
            pending.set()
        if acquired:
            _slots.release()
