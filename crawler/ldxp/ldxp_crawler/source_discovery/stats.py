from __future__ import annotations

import json

from .models import DiscoveryRunStats


def json_summary(stats: DiscoveryRunStats) -> str:
    return json.dumps(
        {
            "status": "succeeded",
            "discovered_raw": stats.discovered_raw_count,
            "normalized": stats.normalized_count,
            "duplicates": stats.duplicate_count,
            "new_candidates": stats.new_candidate_count,
            "reverified": stats.reverified_count,
            "by_adapter": stats.adapter_stats,
        },
        ensure_ascii=False,
    )
