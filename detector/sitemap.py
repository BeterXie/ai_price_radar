from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ElementTree
from collections import deque

from price_radar_http import PinnedHTTPSClient


DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_SITEMAPS = 32
DEFAULT_MAX_PAGES = 8


def sitemap_locations(body: bytes) -> tuple[str, list[str]]:
    """Parse a sitemap body; rejects DTD/entity declarations and non-sitemap XML."""
    lowered = body.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("sitemap must not contain DTD or entity declarations")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("sitemap is invalid XML") from exc
    kind = root.tag.rsplit("}", 1)[-1].casefold()
    if kind not in {"urlset", "sitemapindex"}:
        raise ValueError("source is not a sitemap or sitemap index")
    locations = [
        str(node.text or "").strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].casefold() == "loc" and str(node.text or "").strip()
    ]
    return kind, locations


def _same_origin_url(value: object, origin: str, client: PinnedHTTPSClient) -> str | None:
    try:
        normalized = client.normalize_url(value)
    except ValueError:
        return None
    parsed = urllib.parse.urlsplit(normalized)
    expected = urllib.parse.urlsplit(origin)
    if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
        return None
    return normalized


def product_page_urls(
    entry_url: str,
    origin: str,
    client: PinnedHTTPSClient,
    *,
    preloaded: object | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_sitemaps: int = DEFAULT_MAX_SITEMAPS,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[str]:
    """Bounded, same-origin recursive sitemap traversal returning product page URLs."""
    queue: deque[tuple[str, int]] = deque([(entry_url, 0)])
    seen_sitemaps = {entry_url}
    seen_pages: set[str] = set()
    page_urls: list[str] = []
    while queue:
        current_url, depth = queue.popleft()
        if preloaded is not None and current_url == entry_url:
            response = preloaded
            preloaded = None
        else:
            response = client.get(current_url, accept="application/xml,text/xml;q=0.9,*/*;q=0.1")
        kind, locations = sitemap_locations(response.body)
        if kind == "sitemapindex":
            if depth >= max_depth and locations:
                raise ValueError("sitemap index exceeds recursion depth limit")
            for raw_location in locations:
                child = _same_origin_url(raw_location, origin, client)
                if child is None or child in seen_sitemaps:
                    continue
                seen_sitemaps.add(child)
                if len(seen_sitemaps) > max_sitemaps:
                    raise ValueError("sitemap count limit exceeded")
                queue.append((child, depth + 1))
            continue
        if kind != "urlset":
            raise ValueError("sitemap child is not a urlset")
        for raw_location in locations:
            page = _same_origin_url(raw_location, origin, client)
            if page is None or page in seen_pages:
                continue
            seen_pages.add(page)
            if len(seen_pages) > max_pages:
                raise ValueError("product page count limit exceeded")
            page_urls.append(page)
    return page_urls
