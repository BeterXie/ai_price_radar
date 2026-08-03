from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url


class SeedAdapter(DiscoveryAdapter):
    name = "seed"

    def __init__(self, seeds: Sequence[str] = (), seed_file: Path | None = None):
        self.seeds = list(seeds)
        self.seed_file = seed_file

    def _values(self) -> Iterable[str]:
        yield from self.seeds
        if self.seed_file is not None and self.seed_file.exists():
            for line in self.seed_file.read_text("utf-8-sig", errors="ignore").splitlines():
                value = line.strip()
                if value and not value.lstrip().startswith("#"):
                    yield value

    def discover(
        self,
        *,
        keywords: Iterable[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        for value in self._values():
            try:
                normalized = normalize_candidate_url(value)
            except (TypeError, ValueError):
                continue
            yield DiscoveredCandidate(
                url=normalized,
                discovered_by="seed",
                platform_hint="unknown",
            )
