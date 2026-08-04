from __future__ import annotations

import json
import os
import signal
import time
import urllib.error
import urllib.request
from typing import Any

from probe import MAX_TASK_SECONDS, probe_source
from qualify import QualificationResult, qualify_candidate


API_URL = os.getenv("DETECTOR_API_URL", "http://api:8000").rstrip("/")
WORKER_KEY = os.getenv("DETECTOR_WORKER_KEY", "")
DISCOVERY_WORKER_KEY = os.getenv("DISCOVERY_WORKER_KEY", "")
POLL_SECONDS = max(1.0, float(os.getenv("DETECTOR_POLL_SECONDS", "5")))
CANDIDATE_CLAIM_LIMIT = max(1, int(os.getenv("DISCOVERY_CLAIM_LIMIT", "5")))
CANDIDATE_LEASE_SECONDS = max(60, int(os.getenv("DISCOVERY_LEASE_SECONDS", "900")))


def _probe_with_timeout(source_url: str, *, timeout_seconds: float = MAX_TASK_SECONDS):
    """Enforce a wall-clock limit around DNS resolution and all probe I/O."""
    if not hasattr(signal, "setitimer"):
        return probe_source(source_url)

    def raise_timeout(_signum, _frame):
        raise TimeoutError("source detection exceeded total time limit")

    previous_handler = signal.signal(signal.SIGALRM, raise_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return probe_source(source_url)
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def _request(
    path: str,
    payload: dict[str, Any],
    *,
    worker_key: str = WORKER_KEY,
    header_name: str = "X-Detector-Worker-Key",
) -> Any:
    request = urllib.request.Request(
        API_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            header_name: worker_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_once() -> int:
    processed = 0
    if WORKER_KEY:
        tasks = _request("/api/v1/internal/source-detections/claim", {"limit": 10, "lease_seconds": 300})
        for task in tasks:
            try:
                result = _probe_with_timeout(task["source_url"])
                payload = {
                    "status": "pending_review",
                    "attempt_count": task["attempt_count"],
                    "detected_platform": result.detected_platform,
                    "source_url": result.source_url,
                    "source_key": result.source_key,
                    "shop_name": result.shop_name,
                    "product_count": result.product_count,
                }
            except Exception:
                payload = {
                    "status": "validation_failed",
                    "attempt_count": task["attempt_count"],
                    "failure_reason": "source detection failed",
                }
            _request(f"/api/v1/internal/source-detections/{task['intake_id']}/result", payload)
            processed += 1

    if DISCOVERY_WORKER_KEY:
        candidates = _request(
            "/api/v1/internal/source-candidates/claim",
            {"limit": CANDIDATE_CLAIM_LIMIT, "lease_seconds": CANDIDATE_LEASE_SECONDS},
            worker_key=DISCOVERY_WORKER_KEY,
            header_name="X-Discovery-Worker-Key",
        )
        for task in candidates:
            try:
                result: QualificationResult = qualify_candidate(
                    task["canonical_url"],
                    task["platform_hint"],
                )
                payload = {
                    "status": result.status,
                    "attempt_count": task["attempt_count"],
                    "detected_platform": result.detected_platform,
                    "detected_source_key": result.detected_source_key,
                    "detected_source_url": result.detected_source_url,
                    "total_product_count": result.total_product_count,
                    "ai_product_count": result.ai_product_count,
                    "sample_products": result.sample_products,
                    "fingerprints": result.fingerprints,
                    "confidence_score": result.confidence_score,
                    "failure_reason": result.failure_reason,
                }
            except Exception:
                payload = {
                    "status": "validation_failed",
                    "attempt_count": task["attempt_count"],
                    "detected_platform": "unknown",
                    "detected_source_key": "",
                    "detected_source_url": "",
                    "total_product_count": 0,
                    "ai_product_count": 0,
                    "sample_products": [],
                    "fingerprints": [],
                    "confidence_score": 0,
                    "failure_reason": "candidate qualification failed",
                }
            _request(
                f"/api/v1/internal/source-candidates/{task['candidate_id']}/result",
                payload,
                worker_key=DISCOVERY_WORKER_KEY,
                header_name="X-Discovery-Worker-Key",
            )
            processed += 1
    return processed


def main() -> int:
    if not WORKER_KEY and not DISCOVERY_WORKER_KEY:
        raise SystemExit("at least one of DETECTOR_WORKER_KEY or DISCOVERY_WORKER_KEY is required")
    while True:
        try:
            processed = run_once()
        except (OSError, urllib.error.URLError, ValueError) as exc:
            print(f"detector worker error: {exc}", flush=True)
            processed = 0
        if processed == 0:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
