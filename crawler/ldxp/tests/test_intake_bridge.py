from __future__ import annotations

import json
from pathlib import Path

from ldxp_crawler.db import StateDB
from ldxp_crawler.intake_bridge import IntakeBridge
from ldxp_crawler.models import ProductMatch, ShopScanResult
from ldxp_gpt_crawler import intake_claim_token, intake_result_payload


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_intake_candidate_is_high_priority_and_keeps_attempt_metadata(tmp_path: Path):
    db = StateDB(tmp_path / "crawler.db")
    try:
        db.upsert_candidate("discovered", "https://pay.ldxp.cn/shop/discovered", "seed", 1)
        db.upsert_intake_candidate(
            intake_id=42,
            token="manual",
            url="https://pay.ldxp.cn/shop/manual",
            shop_name="人工申请",
            attempt_count=3,
        )
        candidates = db.list_candidates(limit=1)
        assert candidates[0]["token"] == "manual"
        assert candidates[0]["intake_id"] == 42
        assert candidates[0]["intake_attempt_count"] == 3
    finally:
        db.close()


def test_intake_claim_keeps_original_token_case(tmp_path: Path):
    source_url = "https://pay.ldxp.cn/shop/ABC123"
    token = intake_claim_token(source_url)
    assert token == "ABC123"
    db = StateDB(tmp_path / "crawler.db")
    try:
        db.upsert_intake_candidate(
            intake_id=43,
            token=token,
            url=source_url,
            shop_name="人工申请",
            attempt_count=1,
        )
        row = db.conn.execute("SELECT token FROM candidates WHERE intake_id=43").fetchone()
        assert row[0] == "ABC123"
    finally:
        db.close()


def test_reported_intake_attempt_is_cleared_for_a_new_claim(tmp_path: Path):
    db = StateDB(tmp_path / "crawler.db")
    try:
        db.upsert_intake_candidate(
            intake_id=43,
            token="ABC123",
            url="https://pay.ldxp.cn/shop/ABC123",
            shop_name="人工申请",
            attempt_count=1,
        )
        assert db.mark_intake_result_reported(token="ABC123", intake_id=43, attempt_count=1)
        row = db.conn.execute(
            "SELECT intake_reported_attempt_count FROM candidates WHERE token='ABC123'"
        ).fetchone()
        assert row[0] == 1

        db.upsert_intake_candidate(
            intake_id=43,
            token="ABC123",
            url="https://pay.ldxp.cn/shop/ABC123",
            shop_name="人工申请",
            attempt_count=2,
        )
        row = db.conn.execute(
            "SELECT intake_attempt_count, intake_reported_attempt_count FROM candidates WHERE token='ABC123'"
        ).fetchone()
        assert tuple(row) == (2, None)
    finally:
        db.close()


def test_scan_results_map_to_validated_no_products_and_failure():
    success = ShopScanResult(
        token="shop",
        status="success",
        matches=[ProductMatch(product_key="1", product_name="ChatGPT Plus", matched_keywords=["gpt"])],
    )
    no_products = ShopScanResult(token="shop", status="no_match")
    failed = ShopScanResult(
        token="shop",
        status="network_error",
        error="https://private.example/item?password=secret",
    )
    assert intake_result_payload(success) == ("validated", 1, "")
    assert intake_result_payload(no_products) == ("no_products", 0, "")
    failure_payload = intake_result_payload(failed)
    assert failure_payload == ("validation_failed", 0, "来源暂时无法访问")
    assert "secret" not in failure_payload[2]
    assert "private.example" not in failure_payload[2]


def test_bridge_claim_and_result_use_worker_key(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if request.full_url.endswith("/claim"):
            return FakeResponse([{
                "intake_id": 7,
                "source_key": "manual",
                "source_url": "https://pay.ldxp.cn/shop/manual",
                "attempt_count": 1,
            }])
        return FakeResponse({"status": "validated"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    bridge = IntakeBridge("http://api:8000", "worker-secret")
    claims = bridge.claim(limit=1, lease_seconds=60)
    result = bridge.report_result(
        intake_id=7,
        attempt_count=1,
        status="validated",
        product_count=2,
    )
    assert claims[0]["intake_id"] == 7
    assert result["status"] == "validated"
    assert requests[0][0].headers["X-intake-worker-key"] == "worker-secret"
