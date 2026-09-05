from __future__ import annotations

import urllib.parse
from collections import deque

from defusedxml import ElementTree

from price_radar_http import PinnedHTTPSClient


DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_SITEMAPS = 32
DEFAULT_MAX_PAGES = 8


def sitemap_locations(body: bytes) -> tuple[str, list[str]]:
    """Parse a sitemap body; rejects DTD/entity declarations and non-sitemap XML."""
    try:
        root = ElementTree.fromstring(body, forbid_dtd=True)
    except ElementTree.ParseError as exc:
        raise ValueError("sitemap is invalid XML") from exc
    kind = root.tag.rsplit("}", 1)[-1].casefold()
    if kind not in {"urlset", "sitemapindex"}:
        raise ValueError("source is not a sitemap or sitemap index")
    namespace = root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""
    child = "url" if kind == "urlset" else "sitemap"
    locations = [
        str(node.text or "").strip()
        for node in root.findall(f"{namespace}{child}/{namespace}loc")
        if str(node.text or "").strip()
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
        if response.status != 200:
            raise ValueError(f"sitemap returned HTTP {response.status}")
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
            page_urls.append(page)
            if len(page_urls) >= max_pages:
                # max_pages 是抽样预算：达到后停止收集，不拒绝合法来源。
                return page_urls
    return page_urls
