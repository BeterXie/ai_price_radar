from __future__ import annotations

import os
import json
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .utils import utc_now


@dataclass(frozen=True, slots=True)
class CollectionDecision:
    allowed: bool
    mode: str
    reason: str
    next_allowed_at: Optional[str] = None


OriginCheckResult = Callable[[str], CollectionDecision]


def candidate_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url or ""))
    host = parsed.hostname or ""
    rendered_host = f"[{host}]" if ":" in host else host
    return urllib.parse.urlunsplit(("https", rendered_host, "", "", ""))


class CollectionPolicyGate:
    """Ordered policy gate for every LDXP shop request.

    Check order: master switch, sticky source status (opt-out / legal hold /
    unsupported), robots/terms signal, recent HTTP status, scan frequency,
    per-shop and global budgets, and allowed collection mode.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        mode: str | None = None,
        domain_blocklist: tuple[str, ...] = (),
        max_scans_per_shop_day: int | None = None,
        daily_global_budget: int | None = None,
        origin_checker: OriginCheckResult | None = None,
        environ: dict[str, str] | None = None,
    ):
        env = environ if environ is not None else os.environ
        self.enabled = enabled if enabled is not None else env.get("LDXP_COLLECTION_ENABLED", "false").strip().casefold() in {"1", "true", "yes"}
        self.mode = (mode or env.get("LDXP_COLLECTION_MODE", "public_dom")).strip().casefold()
        raw_blocklist = domain_blocklist or tuple(
            value.strip().casefold()
            for value in env.get("LDXP_DOMAIN_BLOCKLIST", "").split(",")
            if value.strip()
        )
        self.domain_blocklist = raw_blocklist
        self.max_scans_per_shop_day = max_scans_per_shop_day if max_scans_per_shop_day is not None else self._env_int(env, "LDXP_MAX_SCANS_PER_SHOP_DAY", 12)
        self.daily_global_budget = daily_global_budget if daily_global_budget is not None else self._env_int(env, "LDXP_DAILY_GLOBAL_REQUEST_BUDGET", 2000)
        self.origin_checker = origin_checker

    @staticmethod
    def _env_int(env: dict[str, str], key: str, default: int) -> int:
        try:
            return max(0, int(env.get(key, str(default))))
        except (TypeError, ValueError):
            return default

    def decide(self, candidate: dict[str, Any]) -> CollectionDecision:
        if not self.enabled:
            return CollectionDecision(False, "off", "LDXP collection disabled by policy")

        origin = candidate_origin(candidate.get("url") or "")
        host = urllib.parse.urlsplit(origin).hostname or ""
        if any(host == blocked or host.endswith("." + blocked) for blocked in self.domain_blocklist):
            return CollectionDecision(False, self.mode, "domain is blocklisted")

        status = str(candidate.get("policy_status") or "active")
        if status in {"opted_out", "legal_hold"}:
            return CollectionDecision(False, self.mode, f"source status is sticky ({status})")
        if status == "unsupported":
            return CollectionDecision(False, self.mode, "source requires login or is unsupported")

        reason = str(candidate.get("policy_reason") or "")
        if reason.startswith("robots-denied"):
            return CollectionDecision(False, self.mode, "robots or platform policy signal denies collection")

        now = utc_now()
        blocked_until = str(candidate.get("blocked_until") or "")
        if blocked_until and blocked_until > now:
            return CollectionDecision(False, self.mode, f"temporarily blocked until {blocked_until}", next_allowed_at=blocked_until)

        next_scan_at = str(candidate.get("next_scan_at") or "")
        if next_scan_at and next_scan_at > now:
            return CollectionDecision(False, self.mode, "shop is not due yet", next_allowed_at=next_scan_at)

        if str(candidate.get("daily_request_date") or "") == now[:10]:
            daily_count = int(candidate.get("daily_request_count") or 0)
            if daily_count >= self.max_scans_per_shop_day:
                return CollectionDecision(False, self.mode, "per-shop daily budget reached")

        if self.mode != "public_dom":
            return CollectionDecision(False, self.mode, "collection mode is not allowed")

        if self.origin_checker is not None:
            try:
                decision = self.origin_checker(origin)
            except Exception:
                # Fail closed: without confirmation we do not scan.
                return CollectionDecision(False, self.mode, "origin policy check unavailable")
            if not decision.allowed:
                return decision

        return CollectionDecision(True, self.mode, "allowed")


class ApiOriginPolicyChecker:
    """Fail-closed origin policy check against the internal source-policy API."""

    def __init__(self, api_url: str, worker_key: str, *, timeout: float = 10.0):
        self.api_url = api_url.rstrip("/")
        self.worker_key = worker_key
        self.timeout = timeout

    def __call__(self, origin: str) -> CollectionDecision:
        if not self.api_url or not self.worker_key:
            return CollectionDecision(False, "public_dom", "origin policy check unavailable")
        url = f"{self.api_url}/api/v1/internal/source-policy/check?source_url={urllib.parse.quote(origin, safe='')}"
        request = urllib.request.Request(url, headers={"X-Discovery-Worker-Key": self.worker_key})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            return CollectionDecision(False, "public_dom", "origin policy check unavailable")
        if not isinstance(payload, dict):
            return CollectionDecision(False, "public_dom", "origin policy check unavailable")
        if payload.get("emergency_stopped") is True:
            return CollectionDecision(False, "public_dom", "emergency stop is active")
        status = str(payload.get("source_status") or "active")
        if status in {"legal_hold", "opted_out"}:
            return CollectionDecision(False, "public_dom", f"source policy status is {status}")
        if payload.get("allowed") is not True:
            return CollectionDecision(False, "public_dom", "origin policy check denied")
        return CollectionDecision(True, "public_dom", "allowed")
