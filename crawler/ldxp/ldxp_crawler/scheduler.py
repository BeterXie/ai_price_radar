from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Sequence

from .db import StateDB
from .policy import CollectionDecision, CollectionPolicyGate, RobotsTxtPolicy
from .utils import utc_now


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
        robots_policy: RobotsTxtPolicy | None = None,
    ):
        self.db = db
        self.gate = gate
        self.scanner_factory = scanner_factory
        self.logger = logger
        self.batch_limit = max(1, batch_limit)
        self.result_callback = result_callback
        self.robots_policy = robots_policy

    def run_once(self, keywords: Sequence[str]) -> dict[str, int]:
        def _remaining(limit: int, used: int) -> Optional[int]:
            if limit <= 0:
                return None
            return max(0, limit - used)

        due = self.db.list_due_candidates(limit=self.batch_limit)
        if not due:
            return {"attempted": 0, "allowed": 0, "deferred": 0, "scanned": 0, "matches": 0}
        today = utc_now()[:10]
        used = int(
            self.db.conn.execute(
                "SELECT COALESCE(SUM(daily_request_count), 0) FROM candidates WHERE daily_request_date=?",
                (today,),
            ).fetchone()[0]
        )
        if self.gate.daily_global_budget and used >= self.gate.daily_global_budget:
            self.logger.warning("global daily request budget reached (%s); this run is deferred", used)
            return {"attempted": 0, "allowed": 0, "deferred": 0, "scanned": 0, "matches": 0}
        scanner = self.scanner_factory()
        run_id = self.db.start_run("scan", list(keywords), "public_dom", {"scheduler": "due-shop"})
        attempted = allowed = deferred = scanned = match_count = 0
        with scanner:
            for candidate in due:
                if self.gate.daily_global_budget and used >= self.gate.daily_global_budget:
                    deferred += 1
                    self.logger.warning("global daily request budget reached; deferring remaining shops")
                    break
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
                today = utc_now()[:10]
                shop_used = (
                    int(candidate.get("daily_request_count") or 0)
                    if str(candidate.get("daily_request_date") or "") == today
                    else 0
                )
                global_remaining = _remaining(self.gate.daily_global_budget, used)
                shop_remaining = _remaining(self.gate.max_requests_per_shop_day, shop_used)
                remaining_budget = min(
                    [value for value in (global_remaining, shop_remaining) if value is not None],
                    default=None,
                )
                if remaining_budget == 0:
                    deferred += 1
                    continue
                if self.robots_policy is not None and self.gate.respect_robots:
                    origin = self.db.conn.execute(
                        "SELECT url FROM candidates WHERE token=?", (candidate["token"],)
                    ).fetchone()
                    source_url = str(origin["url"] if origin else candidate.get("url") or "")
                    robots_allowed, robots_reason, robots_requests = self.robots_policy.evaluate(source_url)
                    if robots_requests > 0:
                        used += robots_requests
                        shop_used += robots_requests
                        self.db.record_daily_request(candidate["token"], count=robots_requests)
                    if not robots_allowed:
                        self.db.set_policy_status(candidate["token"], "active", reason=robots_reason)
                        deferred += 1
                        continue
                    global_remaining = _remaining(self.gate.daily_global_budget, used)
                    shop_remaining = _remaining(self.gate.max_requests_per_shop_day, shop_used)
                    remaining_budget = min(
                        [value for value in (global_remaining, shop_remaining) if value is not None],
                        default=None,
                    )
                if remaining_budget == 0:
                    deferred += 1
                    continue
                if not self.db.claim_due_candidate(candidate["token"]):
                    deferred += 1
                    continue
                self.db.record_daily_scan(candidate["token"])
                result = scanner.scan_shop(candidate, keywords, request_budget=remaining_budget)
                actual_requests = max(0, int(result.request_count or 0))
                used += actual_requests
                if actual_requests > 0:
                    self.db.record_daily_request(candidate["token"], count=actual_requests)
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
                if self.gate.daily_global_budget and used >= self.gate.daily_global_budget:
                    deferred += max(0, len(due) - attempted)
                    self.logger.warning("global daily request budget reached; deferring remaining shops")
                    break
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
