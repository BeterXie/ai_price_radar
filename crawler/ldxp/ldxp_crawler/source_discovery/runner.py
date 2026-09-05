from __future__ import annotations

import logging
from collections.abc import Sequence
from itertools import islice
from typing import Any

from .bridge import DiscoveryBridge
from .models import DiscoveryAdapter, DiscoveryBudget, DiscoveryRunStats
from .normalize import candidate_key_for, normalize_candidate_url


class DiscoveryRunner:
    def __init__(
        self,
        adapters: Sequence[DiscoveryAdapter],
        bridge: DiscoveryBridge,
        *,
        logger: logging.Logger,
        budget: DiscoveryBudget,
        trigger: str = "scheduled",
        keywords: Sequence[str] = (),
    ):
        self.adapters = list(adapters)
        self.bridge = bridge
        self.logger = logger
        self.budget = budget
        self.trigger = trigger
        self.keywords = tuple(keywords)
        self.stats = DiscoveryRunStats()
        self._seen_keys: set[str] = set()

    def run(self) -> DiscoveryRunStats:
        run_id: int | None = None
        try:
            run_id = self.bridge.create_run(
                trigger=self.trigger,
                adapters=[adapter.name for adapter in self.adapters],
            )
            self.stats.note = f"run_id={run_id}"
        except Exception as exc:
            self.logger.error("创建发现运行失败：%s", type(exc).__name__)
            self.stats.failure_stats["run_create"] = self.stats.failure_stats.get("run_create", 0) + 1
            self.stats.note = "run create failed; candidates will not be submitted"
            return self.stats

        batch: list[dict[str, Any]] = []

        def flush() -> None:
            if not batch:
                return
            for attempt in range(2):
                try:
                    results = self.bridge.batch_upsert(list(batch))
                    for result in results:
                        if result.get("is_new") is True:
                            self.stats.new_candidate_count += 1
                        else:
                            self.stats.duplicate_count += 1
                except Exception as exc:
                    if attempt == 0:
                        self.logger.warning("批量提交候选失败，准备重试：%s", type(exc).__name__)
                        continue
                    self.logger.error("批量提交候选失败：%s", type(exc).__name__)
                    self.stats.failure_stats["batch_upsert"] = self.stats.failure_stats.get("batch_upsert", 0) + 1
                    return
                batch.clear()
                return

        try:
            for adapter in self.adapters:
                if self.stats.discovered_raw_count >= self.budget.max_raw_urls:
                    self.stats.note = "raw URL budget reached"
                    break
                if len(self._seen_keys) >= self.budget.max_unique_candidates:
                    self.stats.note = "unique candidate budget reached"
                    break
                adapter_found = 0
                try:
                    candidates = adapter.discover(keywords=self.keywords, budget=self.budget)
                    for candidate in islice(candidates, self.budget.max_raw_urls - self.stats.discovered_raw_count):
                        self.stats.discovered_raw_count += 1
                        try:
                            normalized = normalize_candidate_url(candidate.url)
                        except (TypeError, ValueError):
                            self.stats.failure_stats.setdefault("normalize", 0)
                            self.stats.failure_stats["normalize"] += 1
                            continue
                        key = candidate_key_for(normalized, candidate.platform_hint)
                        if key in self._seen_keys:
                            self.stats.duplicate_count += 1
                            continue
                        self._seen_keys.add(key)
                        self.stats.normalized_count += 1
                        adapter_found += 1
                        batch.append({
                            "run_id": run_id,
                            "discovered_url": normalized,
                            "platform_hint": candidate.platform_hint,
                            "discovered_by": candidate.discovered_by,
                            "matched_query": candidate.matched_query,
                        })
                        if len(batch) >= 100:
                            flush()
                        if len(self._seen_keys) >= self.budget.max_unique_candidates:
                            self.stats.note = "unique candidate budget reached"
                            break
                except Exception as exc:
                    self.logger.error("Adapter %s 失败：%s", adapter.name, type(exc).__name__)
                    self.stats.failure_stats[adapter.name] = self.stats.failure_stats.get(adapter.name, 0) + 1
                else:
                    self.stats.adapter_stats[adapter.name] = adapter_found
            flush()
        finally:
            payload = {
                "status": "succeeded" if not self.stats.failure_stats else "partial",
                "discovered_raw_count": self.stats.discovered_raw_count,
                "normalized_count": self.stats.normalized_count,
                "duplicate_count": self.stats.duplicate_count,
                "new_candidate_count": self.stats.new_candidate_count,
                "reverified_count": self.stats.reverified_count,
                "detected_count": self.stats.detected_count,
                "ai_matched_count": self.stats.ai_matched_count,
                "auto_approved_count": self.stats.auto_approved_count,
                "pending_review_count": self.stats.pending_review_count,
                "validation_failed_count": self.stats.validation_failed_count,
                "promoted_intake_count": self.stats.promoted_intake_count,
                "adapter_stats": self.stats.adapter_stats,
                "platform_stats": self.stats.platform_stats,
                "failure_stats": self.stats.failure_stats,
                "note": self.stats.note,
            }
            if run_id is not None:
                try:
                    self.bridge.finish_run(run_id, payload)
                except Exception as exc:
                    self.logger.error("结束发现运行失败：%s", type(exc).__name__)
                    self.stats.failure_stats["run_finish"] = self.stats.failure_stats.get("run_finish", 0) + 1
        return self.stats
