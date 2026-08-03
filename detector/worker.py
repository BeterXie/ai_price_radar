from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from probe import probe_source


API_URL = os.getenv("DETECTOR_API_URL", "http://api:8000").rstrip("/")
WORKER_KEY = os.getenv("DETECTOR_WORKER_KEY", "")
POLL_SECONDS = max(1.0, float(os.getenv("DETECTOR_POLL_SECONDS", "5")))


def _request(path: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        API_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Detector-Worker-Key": WORKER_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_once() -> int:
    tasks = _request("/api/v1/internal/source-detections/claim", {"limit": 10, "lease_seconds": 300})
    for task in tasks:
        try:
            result = probe_source(task["source_url"])
            payload = {
                "status": "pending_review",
                "attempt_count": task["attempt_count"],
                "detected_platform": result.detected_platform,
                "source_url": result.source_url,
                "source_key": result.source_key,
                "shop_name": result.shop_name,
                "product_count": result.product_count,
            }
        except Exception as exc:
            payload = {
                "status": "validation_failed",
                "attempt_count": task["attempt_count"],
                "failure_reason": str(exc)[:500],
            }
        _request(f"/api/v1/internal/source-detections/{task['intake_id']}/result", payload)
    return len(tasks)


def main() -> int:
    if not WORKER_KEY:
        raise SystemExit("DETECTOR_WORKER_KEY is required")
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
