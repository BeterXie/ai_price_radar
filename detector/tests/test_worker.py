import signal
import time
from pathlib import Path

import pytest

import worker
from qualify import QualificationResult


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="production detector runs on Linux")
def test_probe_timeout_includes_blocking_resolver_time(monkeypatch):
    monkeypatch.setattr(worker, "probe_source", lambda _url: time.sleep(1))
    started_at = time.monotonic()
    with pytest.raises(TimeoutError, match="total time limit"):
        worker._probe_with_timeout("https://slow.example", timeout_seconds=0.01)
    assert time.monotonic() - started_at < 0.5


def test_run_once_claims_and_reports_candidate_tasks(monkeypatch):
    requests: list[tuple[str, dict]] = []

    def fake_request(path: str, payload: dict, **kwargs):
        requests.append((path, payload))
        if path.endswith("/source-detections/claim"):
            return []
        if path.endswith("/source-candidates/claim"):
            return [{
                "candidate_id": 7,
                "canonical_url": "https://woo.example.com/products/chatgpt",
                "platform_hint": "unknown",
                "attempt_count": 2,
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
            }]
        if path.endswith("/source-candidates/7/result"):
            return {"candidate_id": 7, "status": "promoted"}
        return {}

    monkeypatch.setattr(worker, "DISCOVERY_WORKER_KEY", "discovery-test")
    monkeypatch.setattr(worker, "_request", fake_request)
    monkeypatch.setattr(
        worker,
        "qualify_candidate",
        lambda url, hint: QualificationResult(
            status="detected",
            detected_platform="woocommerce",
            detected_source_key="https://woo.example.com",
            detected_source_url="https://woo.example.com",
            total_product_count=1,
            ai_product_count=1,
            sample_products=[{"name": "ChatGPT Plus", "url": "https://woo.example.com/p/1"}],
            fingerprints=["woocommerce-store-api"],
            confidence_score=88,
        ),
    )
    processed = worker.run_once()
    assert processed == 1
    claim_call = next(item for item in requests if item[0].endswith("/source-candidates/claim"))
    assert claim_call[1] == {"limit": 5, "lease_seconds": 900}
    result_call = next(item for item in requests if item[0].endswith("/source-candidates/7/result"))
    assert result_call[1]["attempt_count"] == 2
    assert result_call[1]["status"] in {"detected", "no_match", "validation_failed"}
