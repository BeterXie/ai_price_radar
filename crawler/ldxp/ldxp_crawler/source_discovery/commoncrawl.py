from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

import requests

from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url, platform_hint_for_candidate


COMMONCRAWL_INDEX_URL = "https://index.commoncrawl.org/collinfo.json"
CDX_PATTERNS = (
    "pay.ldxp.cn/shop/*",
    "16688.com.cn/shop/*",
    "www.16688.com.cn/shop/*",
)


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
        emitted = 0
        for index in indexes[: max(0, budget.max_cc_indexes)]:
            api = index.get("cdx-api") if isinstance(index, dict) else None
            if not api:
                continue
            for pattern in CDX_PATTERNS:
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
                            yield DiscoveredCandidate(
                                url=normalized,
                                discovered_by=f"commoncrawl:{index.get('id', '') if isinstance(index, dict) else ''}",
                                platform_hint=platform_hint_for_candidate(normalized),
                            )
                            emitted += 1
                            if emitted >= max(0, budget.max_cc_urls):
                                return
                except requests.RequestException:
                    continue
