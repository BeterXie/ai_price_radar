from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Sequence

from .db import StateDB
from .policy import CollectionDecision, CollectionPolicyGate


class DueShopScheduler:
    """Adaptive due-shop scheduler.

    The systemd timer only wakes this scheduler; the real per-shop frequency is
    driven by ``next_scan_at`` / ``scan_interval_minutes`` maintained by the
    policy gate and scan results.
    """

    def __init__(
        self,
        db: StateDB,
        gate: CollectionPolicyGate,
        scanner_factory: Callable[[], Any],
        logger: logging.Logger,
        *,
        batch_limit: int = 20,
        result_callback: Callable[[Any, dict[str, Any]], None] | None = None,
    ):
        self.db = db
        self.gate = gate
        self.scanner_factory = scanner_factory
        self.logger = logger
        self.batch_limit = max(1, batch_limit)
        self.result_callback = result_callback

    def run_once(self, keywords: Sequence[str]) -> dict[str, int]:
        due = self.db.list_due_candidates(limit=self.batch_limit)
        if not due:
            return {"attempted": 0, "allowed": 0, "deferred": 0, "scanned": 0, "matches": 0}
        scanner = self.scanner_factory()
        run_id = self.db.start_run("scan", list(keywords), "public_dom", {"scheduler": "due-shop"})
        attempted = allowed = deferred = scanned = match_count = 0
        with scanner:
            for candidate in due:
                attempted += 1
                decision = self.gate.decide(candidate)
                if not decision.allowed:
                    deferred += 1
                    self.logger.info(
                        "Due shop %s deferred: %s",
                        candidate["token"],
                        decision.reason,
                    )
                    continue
                allowed += 1
                if not self.db.claim_due_candidate(candidate["token"]):
                    deferred += 1
                    continue
                self.db.record_daily_request(candidate["token"])
                result = scanner.scan_shop(candidate, keywords)
                self.db.save_scan_result(result, run_id)
                if self.result_callback is not None:
                    self.result_callback(result, candidate)
                scanned += 1
                match_count += len(result.matches)
                self.logger.info(
                    "Due shop %s status=%s products=%s matches=%s",
                    result.token,
                    result.status,
                    result.scanned_item_count,
                    len(result.matches),
                )
        self.db.finish_run(
            run_id,
            attempted=attempted,
            successful=scanned,
            failed=0,
            blocked=0,
            matches=match_count,
            circuit_broken=False,
            note=f"due scheduler: allowed={allowed} deferred={deferred}",
        )
        return {
            "attempted": attempted,
            "allowed": allowed,
            "deferred": deferred,
            "scanned": scanned,
            "matches": match_count,
        }
