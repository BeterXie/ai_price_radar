from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

import requests

from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url, platform_hint_for_candidate


COMMONCRAWL_INDEX_URL = "https://index.commoncrawl.org/collinfo.json"
CDX_PATTERNS = {
    "ldxp": ("pay.ldxp.cn/shop/*",),
    "16688": (
        "16688.com.cn/shop/*",
        "www.16688.com.cn/shop/*",
    ),
}


def _pattern_budgets(max_urls: int) -> list[tuple[str, int]]:
    """Reserve Common Crawl capacity for each supported storefront platform."""
    max_urls = max(0, int(max_urls))
    platform_count = len(CDX_PATTERNS)
    if platform_count == 0:
        return []
    per_platform, platform_remainder = divmod(max_urls, platform_count)
    budgets: list[tuple[str, int]] = []
    for platform_index, patterns in enumerate(CDX_PATTERNS.values()):
        platform_budget = per_platform + int(platform_index < platform_remainder)
        per_pattern, pattern_remainder = divmod(platform_budget, len(patterns))
        budgets.extend(
            (pattern, per_pattern + int(pattern_index < pattern_remainder))
            for pattern_index, pattern in enumerate(patterns)
        )
    return budgets


class CommonCrawlAdapter(DiscoveryAdapter):
    name = "commoncrawl"

    def __init__(self, session: requests.Session, *, timeout: float):
        self.session = session
        self.timeout = timeout

    def discover(
        self,
        *,
        keywords: Sequence[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        try:
            response = self.session.get(COMMONCRAWL_INDEX_URL, timeout=self.timeout)
            response.raise_for_status()
            indexes = response.json()
        except (requests.RequestException, ValueError):
            return
        if not isinstance(indexes, list):
            return
        pattern_budgets = _pattern_budgets(budget.max_cc_urls)
        emitted_by_pattern = {pattern: 0 for pattern, _ in pattern_budgets}
        for index in indexes[: max(0, budget.max_cc_indexes)]:
            api = index.get("cdx-api") if isinstance(index, dict) else None
            if not api:
                continue
            for pattern, pattern_budget in pattern_budgets:
                if pattern_budget <= 0 or emitted_by_pattern[pattern] >= pattern_budget:
                    continue
                params = [
                    ("url", pattern),
                    ("output", "json"),
                    ("filter", "status:200"),
                    ("filter", "mime:text/html"),
                    ("collapse", "urlkey"),
                ]
                try:
                    with self.session.get(
                        api,
                        params=params,
                        timeout=max(self.timeout, 60),
                        stream=True,
                    ) as response:
                        if response.status_code != 200:
                            continue
                        for raw_line in response.iter_lines(decode_unicode=True):
                            if emitted_by_pattern[pattern] >= pattern_budget:
                                break
                            if not raw_line:
                                continue
                            try:
                                row = json.loads(raw_line)
                            except json.JSONDecodeError:
                                continue
                            raw_url = row.get("url", "") if isinstance(row, dict) else ""
                            try:
                                normalized = normalize_candidate_url(raw_url)
                            except (TypeError, ValueError):
                                continue
                            emitted_by_pattern[pattern] += 1
                            yield DiscoveredCandidate(
                                url=normalized,
                                discovered_by=f"commoncrawl:{index.get('id', '') if isinstance(index, dict) else ''}",
                                platform_hint=platform_hint_for_candidate(normalized),
                            )
                except requests.RequestException:
                    continue
