from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class DiscoveredCandidate:
    url: str
    discovered_by: str
    platform_hint: str = "unknown"
    matched_query: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveryBudget:
    max_raw_urls: int = 2000
    max_unique_candidates: int = 1000
    request_interval_seconds: float = 2.0
    max_bing_pages: int = 5
    max_bing_count: int = 30
    max_github_pages: int = 3
    max_github_count: int = 100
    max_github_candidates: int = 300
    max_cc_indexes: int = 2
    max_cc_urls: int = 500
    max_16688_source_pages: int = 3
    github_token: str = ""


@dataclass(slots=True)
class DiscoveryRunStats:
    discovered_raw_count: int = 0
    normalized_count: int = 0
    duplicate_count: int = 0
    new_candidate_count: int = 0
    reverified_count: int = 0
    detected_count: int = 0
    ai_matched_count: int = 0
    auto_approved_count: int = 0
    pending_review_count: int = 0
    validation_failed_count: int = 0
    promoted_intake_count: int = 0
    adapter_stats: dict[str, int] = field(default_factory=dict)
    platform_stats: dict[str, int] = field(default_factory=dict)
    failure_stats: dict[str, int] = field(default_factory=dict)
    note: str = ""


class DiscoveryAdapter:
    name: str

    def discover(
        self,
        *,
        keywords: Iterable[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        raise NotImplementedError
