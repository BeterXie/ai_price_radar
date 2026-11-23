from __future__ import annotations

import json
import os
import signal
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any

from probe import MAX_TASK_SECONDS, MAX_RESPONSE_BYTES, MAX_TASK_BYTES, PLATFORM_16688_HOSTS, probe_source
from price_radar_http import PinnedHTTPSClient
from qualify import QualificationResult, qualify_candidate, MAX_TASK_BYTES as QUALIFICATION_MAX_BYTES
from price_radar_http.pacing import OriginCoolingDown


API_URL = os.getenv("DETECTOR_API_URL", "http://api:8000").rstrip("/")
def _secret(name):
    path = os.getenv(name + "_FILE")
    value = Path(path).read_text().strip() if path else os.getenv(name, "")
    if path and not value:
        raise RuntimeError(name + '_FILE is empty')
    return value


WORKER_KEY = _secret("DETECTOR_WORKER_KEY")
DISCOVERY_WORKER_KEY = _secret("DISCOVERY_WORKER_KEY")
POLL_SECONDS = max(1.0, float(os.getenv("DETECTOR_POLL_SECONDS", "5")))
CANDIDATE_CLAIM_LIMIT = max(1, int(os.getenv("DISCOVERY_CLAIM_LIMIT", "5")))
CANDIDATE_LEASE_SECONDS = max(60, int(os.getenv("DISCOVERY_LEASE_SECONDS", "900")))
DETECTOR_SCOPE = os.getenv('DETECTOR_SCOPE', 'all')
if DETECTOR_SCOPE not in {'all', '16688', 'other'}:
    raise RuntimeError('DETECTOR_SCOPE must be all, 16688 or other')


def is_16688(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').encode('idna').decode('ascii').casefold().rstrip('.')
        return parsed.scheme.casefold() == 'https' and parsed.port in (None, 443) and host in PLATFORM_16688_HOSTS
    except (ValueError, UnicodeError):
        return False


def accepts_source(url: str) -> bool:
    return DETECTOR_SCOPE == 'all' or is_16688(url) == (DETECTOR_SCOPE == '16688')


def report_result(path, payload, **kwargs):
    try:
        _request(path, payload, **kwargs)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 409, 422):
            raise
        # One stale/rejected result must not abandon the rest of the claim.
        print(f'Detector result deferred: path={path} status={exc.code}', flush=True)
        return False


def _probe_with_timeout(source_url: str, *, timeout_seconds: float | None = None):
    """Enforce a wall-clock limit around DNS resolution and all probe I/O."""
    remote_16688 = is_16688(source_url)
    if timeout_seconds is None:
        timeout_seconds = 60.0 if remote_16688 else MAX_TASK_SECONDS
    def probe():
        if remote_16688:
            return probe_source(source_url, client=PinnedHTTPSClient(max_response_bytes=MAX_RESPONSE_BYTES,
                max_task_bytes=MAX_TASK_BYTES, max_task_seconds=timeout_seconds, request_timeout=20,
                user_agent='AI-Price-Radar-Detector/1'))
        return probe_source(source_url)
    if not hasattr(signal, "setitimer"):
        return probe()

    def raise_timeout(_signum, _frame):
        raise TimeoutError("source detection exceeded total time limit")

    previous_handler = signal.signal(signal.SIGALRM, raise_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return probe()
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
        tasks = _request("/api/v1/internal/source-detections/claim", {
            "limit": 10 if DETECTOR_SCOPE == 'other' else 1, "lease_seconds": 300, "scope": DETECTOR_SCOPE})
        for task in tasks:
            if not accepts_source(task['source_url']):
                print(f"Detector scope mismatch: intake={task['intake_id']}", flush=True)
                continue
            try:
                result = _probe_with_timeout(task["source_url"])
                payload = {
                    "status": "pending_review",
                    "attempt_count": task["attempt_count"],
                    "detected_platform": result.detected_platform,
                    "source_url": result.source_url,
                    "source_key": result.source_key,
                    "shop_name": result.shop_name[:120],
                    "product_count": result.product_count,
                }
            except OriginCoolingDown as exc:
                # Leave the lease for expiry, rather than mark a source invalid
                # because another process hit the shared origin budget.
                print(f"Source lease deferred: {exc}", flush=True)
                continue
            except Exception:
                payload = {
                    "status": "validation_failed",
                    "attempt_count": task["attempt_count"],
                    "failure_reason": "source detection failed",
                }
            if report_result(f"/api/v1/internal/source-detections/{task['intake_id']}/result", payload):
                processed += 1
                print(f"Detected intake={task['intake_id']} scope={DETECTOR_SCOPE} status={payload['status']}", flush=True)

    if DISCOVERY_WORKER_KEY:
        candidates = _request(
            "/api/v1/internal/source-candidates/claim",
            {"limit": 1 if DETECTOR_SCOPE == '16688' else CANDIDATE_CLAIM_LIMIT,
             "lease_seconds": CANDIDATE_LEASE_SECONDS, "scope": DETECTOR_SCOPE},
            worker_key=DISCOVERY_WORKER_KEY,
            header_name="X-Discovery-Worker-Key",
        )
        for task in candidates:
            if not accepts_source(task['canonical_url']):
                print(f"Detector scope mismatch: candidate={task['candidate_id']}", flush=True)
                continue
            try:
                qualification_options = {}
                if is_16688(task['canonical_url']):
                    qualification_options['client'] = PinnedHTTPSClient(max_response_bytes=MAX_RESPONSE_BYTES,
                        max_task_bytes=QUALIFICATION_MAX_BYTES, max_task_seconds=60, request_timeout=20,
                        user_agent='AI-Price-Radar-Detector/3.7')
                result: QualificationResult = qualify_candidate(
                    task["canonical_url"],
                    task["platform_hint"],
                    **qualification_options,
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
            except OriginCoolingDown as exc:
                print(f"Candidate lease deferred: {exc}", flush=True)
                continue
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
            reported = report_result(
                f"/api/v1/internal/source-candidates/{task['candidate_id']}/result",
                payload,
                worker_key=DISCOVERY_WORKER_KEY,
                header_name="X-Discovery-Worker-Key",
            )
            processed += int(reported)
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
