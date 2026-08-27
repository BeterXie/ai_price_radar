from __future__ import annotations

import random
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from typing import Any

import requests

from .keywords import bing_16688_queries, bing_schema_org_queries, bing_woocommerce_queries
from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url, platform_hint_for_candidate


def extract_bing_result_urls(content: bytes) -> list[str]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    urls: list[str] = []
    for item in root.findall(".//item"):
        raw = item.findtext("link") or ""
        try:
            normalized = normalize_candidate_url(raw)
        except (TypeError, ValueError):
            continue
        if normalized not in urls:
            urls.append(normalized)
    return urls


class BingAdapter(DiscoveryAdapter):
    name = "bing"

    def __init__(
        self,
        session: requests.Session,
        *,
        timeout: float,
    ):
        self.session = session
        self.timeout = timeout

    def _fetch(self, url: str) -> list[str]:
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException:
            return []
        if response.status_code != 200:
            return []
        return extract_bing_result_urls(response.content)

    def discover(
        self,
        *,
        keywords: Sequence[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        queries = [
            *bing_woocommerce_queries(keywords),
            *bing_schema_org_queries(keywords),
            *bing_16688_queries(keywords),
        ]
        seen: set[str] = set()
        for query in queries:
            if query in seen:
                continue
            seen.add(query)
            for page in range(max(1, budget.max_bing_pages)):
                params = {
                    "q": query,
                    "format": "rss",
                    "count": min(max(budget.max_bing_count, 10), 50),
                    "first": 1 + page * budget.max_bing_count,
                    "setlang": "zh-Hans",
                }
                url = "https://www.bing.com/search?" + urllib.parse.urlencode(params)
                urls = self._fetch(url)
                if not urls:
                    break
                for raw in urls:
                    try:
                        normalized = normalize_candidate_url(raw)
                    except (TypeError, ValueError):
                        continue
                    yield DiscoveredCandidate(
                        url=normalized,
                        discovered_by=f"bing:{query}",
                        platform_hint=platform_hint_for_candidate(normalized),
                        matched_query=query,
                    )
                time.sleep(max(0.0, budget.request_interval_seconds) + random.uniform(0, 0.4))
