from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import Base as ApiBase, get_db
from app.main import app
from app.models import SourceCandidate, SourceIntake
from app.services.source_discovery import normalize_candidate_url


def make_client(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "discovery.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")
    monkeypatch.setattr(settings, "discovery_worker_key", "discovery-test")
    monkeypatch.setattr(settings, "detector_worker_key", "detector-test")
    monkeypatch.setattr(settings, "discovery_dujiao_auto_approve", True)
    monkeypatch.setattr(settings, "discovery_woocommerce_auto_approve", True)
    monkeypatch.setattr(settings, "discovery_schema_auto_approve", False)
    monkeypatch.setattr(settings, "discovery_merchant_auto_approve", False)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.state.test_engine = engine
    try:
        yield TestClient(app)
    finally:
        app.state.test_engine = None
        app.dependency_overrides.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    yield from make_client(tmp_path, monkeypatch)


@pytest.fixture
def engine(client):
    return client.app.state.test_engine


DISCOVERY_HEADERS = {"X-Discovery-Worker-Key": "discovery-test"}
ADMIN_HEADERS = {"X-Admin-Key": "admin-test"}


def upsert(client, url, *, hint="unknown", source="bing", query="\"ChatGPT Plus\"", run_id=None):
    payload = {
        "discovered_url": url,
        "platform_hint": hint,
        "discovered_by": source,
        "matched_query": query,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    return client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers=DISCOVERY_HEADERS,
        json=payload,
    )


def claim(client, limit=10):
    return client.post(
        "/api/v1/internal/source-candidates/claim",
        headers=DISCOVERY_HEADERS,
        json={"limit": limit, "lease_seconds": 300},
    ).json()


def report(client, candidate_id, attempt_count, **overrides):
    payload = {
        "status": "detected",
        "attempt_count": attempt_count,
        "detected_platform": "woocommerce",
        "detected_source_key": "https://shop.example.com",
        "detected_source_url": "https://shop.example.com",
        "total_product_count": 12,
        "ai_product_count": 3,
        "sample_products": [{"name": "ChatGPT Plus", "url": "https://shop.example.com/product/chatgpt", "product_slug": "chatgpt-plus"}],
        "fingerprints": ["woocommerce-store-api"],
        "confidence_score": 90,
        "failure_reason": "",
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/internal/source-candidates/{candidate_id}/result",
        headers=DISCOVERY_HEADERS,
        json=payload,
    )


def test_discovery_worker_key_is_independent_and_required(client):
    response = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers={"X-Discovery-Worker-Key": "detector-test"},
        json={"discovered_url": "https://shop.example.com", "discovered_by": "seed"},
    )
    assert response.status_code == 401
    response = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers={"X-Discovery-Worker-Key": "discovery-test"},
        json={"discovered_url": "https://shop.example.com", "discovered_by": "seed"},
    )
    assert response.status_code == 200


def test_upsert_normalizes_and_deduplicates_candidates(client):
    first = upsert(client, "https://Shop.Example.com/products/chatgpt?ref=search", hint="dujiao_next")
    assert first.status_code == 200
    assert first.json()["is_new"] is True
    duplicate = upsert(client, "https://shop.example.com/buy/20", hint="dujiao_next", source="github:owner/repo")
    assert duplicate.status_code == 200
    assert duplicate.json()["is_new"] is False
    assert duplicate.json()["merged"] is True
    assert duplicate.json()["candidate_id"] == first.json()["candidate_id"]


def test_schema_org_candidate_keeps_exact_entry_url(client):
    url = "https://shop.example.com/product-sitemap.xml"
    response = upsert(client, url, hint="schema_org")
    assert response.status_code == 200
    candidate_id = response.json()["candidate_id"]
    detail = client.get(
        f"/api/v1/admin/source-candidates/{candidate_id}",
        headers=ADMIN_HEADERS,
    ).json()
    assert detail["canonical_url"] == url
    assert detail["candidate_key"] != url


def test_batch_upsert_caps_payload_and_returns_each_result(client):
    response = client.post(
        "/api/v1/internal/source-candidates/batch",
        headers=DISCOVERY_HEADERS,
        json={"items": [
            {"discovered_url": f"https://shop-{index}.example.com", "discovered_by": "seed"}
            for index in range(101)
        ]},
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/internal/source-candidates/batch",
        headers=DISCOVERY_HEADERS,
        json={"items": [
            {"discovered_url": f"https://shop-{index}.example.com", "discovered_by": "seed"}
            for index in range(3)
        ]},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 3


def test_claim_returns_each_candidate_once_and_increments_attempt(client):
    upsert(client, "https://one.example.com", hint="dujiao_next")
    upsert(client, "https://two.example.com", hint="woocommerce")
    first = claim(client, limit=1)
    assert len(first) == 1
    assert first[0]["attempt_count"] == 1
    assert first[0]["lease_expires_at"] is not None
    second = claim(client, limit=10)
    assert len(second) == 1
    assert second[0]["candidate_id"] != first[0]["candidate_id"]
    assert claim(client, limit=10) == []


def test_rejected_and_disabled_candidates_never_requeue(client):
    response = upsert(client, "https://sticky.example.com", hint="dujiao_next")
    candidate_id = response.json()["candidate_id"]
    rejected = client.post(
        f"/api/v1/admin/source-candidates/{candidate_id}/reject",
        headers=ADMIN_HEADERS,
        json={"reason": "not a store"},
    )
    assert rejected.json()["status"] == "rejected"
    upsert(client, "https://sticky.example.com/buy/1", hint="dujiao_next", source="github:x")
    assert claim(client) == []

    response = upsert(client, "https://disabled.example.com", hint="dujiao_next")
    candidate_id = response.json()["candidate_id"]
    disabled = client.post(
        f"/api/v1/admin/source-candidates/{candidate_id}/disable",
        headers=ADMIN_HEADERS,
        json={"reason": "disabled by admin"},
    )
    assert disabled.json()["status"] == "disabled"
    upsert(client, "https://disabled.example.com", hint="dujiao_next", source="github:y")
    assert claim(client) == []


def test_failed_candidate_requeues_only_after_backoff(client, engine):
    upsert(client, "https://retry.example.com", hint="dujiao_next")
    task = claim(client)[0]
    response = report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        status="validation_failed",
        detected_platform="unknown",
        failure_reason="timeout",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validation_failed"
    assert claim(client) == []
    with Session(engine) as db:
        candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == task["candidate_id"]))
        candidate.next_verify_at = candidate.next_verify_at - timedelta(days=1)
        db.commit()
    requeued = claim(client)
    assert len(requeued) == 1
    assert requeued[0]["attempt_count"] == 2


def test_stale_attempt_and_expired_lease_are_rejected(client, engine):
    upsert(client, "https://lease.example.com", hint="dujiao_next")
    task = claim(client)[0]
    stale = report(client, task["candidate_id"], task["attempt_count"] + 1)
    assert stale.status_code == 422
    with Session(engine) as db:
        candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == task["candidate_id"]))
        candidate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    expired = report(client, task["candidate_id"], task["attempt_count"])
    assert expired.status_code == 422
    recovered = claim(client)
    assert len(recovered) == 1
    assert recovered[0]["attempt_count"] == 2


def test_woocommerce_auto_approval_promotes_to_approved_intake(client, engine):
    upsert(client, "https://shop.example.com/products/chatgpt", hint="unknown", source="bing")
    task = claim(client)[0]
    response = report(client, task["candidate_id"], task["attempt_count"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    assert body["detected_platform"] == "woocommerce"
    assert body["promoted_intake_id"] is not None
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == body["promoted_intake_id"]))
        assert intake is not None
        assert intake.source_type == "woocommerce"
        assert intake.detected_platform == "woocommerce"
        assert intake.status == "approved"
        assert intake.origin == "discovery"
        assert intake.source_url == "https://shop.example.com"
        assert intake.source_key == "https://shop.example.com"
        assert intake.approved_at is not None
        assert intake.product_count == 3


def test_auto_approval_low_confidence_keeps_intake_pending(client, engine):
    upsert(client, "https://low-confidence.example.com", hint="woocommerce")
    task = claim(client)[0]
    response = report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        confidence_score=49,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == body["promoted_intake_id"]))
        assert intake.status == "pending_review"
        assert intake.approved_at is None


def test_auto_approval_empty_samples_keeps_intake_pending(client, engine):
    upsert(client, "https://no-samples.example.com", hint="woocommerce")
    task = claim(client)[0]
    response = report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        sample_products=[],
        confidence_score=90,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == body["promoted_intake_id"]))
        assert intake.status == "pending_review"
        assert intake.approved_at is None


def test_schema_org_promotes_to_pending_review_intake_by_default(client, engine):
    upsert(client, "https://structured.example.com/product-sitemap.xml", hint="schema_org")
    task = claim(client)[0]
    response = report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        detected_platform="schema_org",
        detected_source_key="https://structured.example.com/product-sitemap.xml",
        detected_source_url="https://structured.example.com/product-sitemap.xml",
        total_product_count=8,
        ai_product_count=2,
        confidence_score=80,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "promoted"
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == response.json()["promoted_intake_id"]))
        assert intake.status == "pending_review"
        assert intake.source_url == "https://structured.example.com/product-sitemap.xml"
        assert intake.detected_platform == "schema_org"


def test_auto_approve_flag_off_keeps_candidate_pending(client, engine):
    settings = get_settings()
    settings.discovery_woocommerce_auto_approve = False
    upsert(client, "https://manual.example.com", hint="woocommerce")
    task = claim(client)[0]
    response = report(client, task["candidate_id"], task["attempt_count"])
    assert response.json()["status"] == "promoted"
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == response.json()["promoted_intake_id"]))
        assert intake.status == "pending_review"
    candidate_id = response.json()["candidate_id"]
    detail = client.get(f"/api/v1/admin/source-candidates/{candidate_id}", headers=ADMIN_HEADERS).json()
    assert "自动审批关闭" in detail["decision_note"]


def test_no_ai_products_and_validation_failed_are_never_promoted(client):
    upsert(client, "https://none.example.com", hint="woocommerce")
    task = claim(client)[0]
    response = report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        ai_product_count=0,
        sample_products=[],
        status="no_match",
        failure_reason="没有可发布的 AI 商品",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_match"
    assert response.json()["promoted_intake_id"] is None


def test_invalid_result_payloads_are_rejected(client):
    upsert(client, "https://invalid.example.com", hint="dujiao_next")
    task = claim(client)[0]
    assert report(client, task["candidate_id"], task["attempt_count"], detected_platform="shopify").status_code == 422
    assert report(client, task["candidate_id"], task["attempt_count"], sample_products=[
        {"name": f"product-{index}", "url": f"https://invalid.example.com/p/{index}"} for index in range(6)
    ]).status_code == 422
    assert report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        confidence_score=101,
    ).status_code == 422
    assert report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        detected_source_url="https://user:pass@invalid.example.com",
    ).status_code == 422


def test_promote_is_idempotent_and_does_not_duplicate_intakes(client, engine):
    upsert(client, "https://idem.example.com", hint="woocommerce")
    task = claim(client)[0]
    first = report(client, task["candidate_id"], task["attempt_count"]).json()
    candidate_id = first["candidate_id"]
    with Session(engine) as db:
        intake_count_before = len(list(db.scalars(select(SourceIntake))))
    promoted = client.post(
        f"/api/v1/admin/source-candidates/{candidate_id}/promote",
        headers=ADMIN_HEADERS,
        json={"reason": "manual retry"},
    )
    assert promoted.status_code == 409
    with Session(engine) as db:
        assert len(list(db.scalars(select(SourceIntake)))) == intake_count_before


def test_admin_candidate_actions_and_filters(client):
    upsert(client, "https://admin-one.example.com", hint="dujiao_next", source="bing")
    upsert(client, "https://admin-two.example.com", hint="schema_org", source="seed")
    rows = client.get(
        "/api/v1/admin/source-candidates",
        headers=ADMIN_HEADERS,
        params={"discovered_by": "bing"},
    ).json()
    assert len(rows) == 1
    assert rows[0]["canonical_url"] == "https://admin-one.example.com/"
    candidate_id = rows[0]["id"]
    detail = client.get(f"/api/v1/admin/source-candidates/{candidate_id}", headers=ADMIN_HEADERS)
    assert detail.status_code == 200
    retried = client.post(
        f"/api/v1/admin/source-candidates/{candidate_id}/retry",
        headers=ADMIN_HEADERS,
        json={"reason": "retry now"},
    )
    assert retried.json()["status"] == "queued"
    tasks = claim(client, limit=10)
    assert any(task["candidate_id"] == candidate_id for task in tasks)
    task = next(task for task in tasks if task["candidate_id"] == candidate_id)
    reported = report(
        client,
        candidate_id,
        task["attempt_count"],
        detected_platform="dujiao_next",
        detected_source_key="https://admin-one.example.com",
        detected_source_url="https://admin-one.example.com",
        ai_product_count=1,
        total_product_count=5,
    )
    assert reported.json()["status"] == "promoted"
    rejected = client.post(
        f"/api/v1/admin/source-candidates/{candidate_id}/reject",
        headers=ADMIN_HEADERS,
        json={"reason": "after review"},
    )
    assert rejected.status_code == 409


def test_admin_manual_promote_creates_approved_intake(client, engine):
    settings = get_settings()
    settings.discovery_woocommerce_auto_approve = False
    upsert(client, "https://manual-promote.example.com", hint="woocommerce")
    task = claim(client)[0]
    reported = report(client, task["candidate_id"], task["attempt_count"]).json()
    assert reported["status"] == "promoted"
    assert reported["promoted_intake_id"] is not None
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == reported["promoted_intake_id"]))
        assert intake.status == "pending_review"


def test_discovery_runs_lifecycle_and_admin_listing(client):
    created = client.post(
        "/api/v1/internal/source-discovery/runs",
        headers=DISCOVERY_HEADERS,
        json={"trigger": "manual", "adapters": ["seed", "bing"]},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]
    response = upsert(client, "https://run.example.com", hint="dujiao_next")
    assert response.status_code == 200
    finished = client.post(
        f"/api/v1/internal/source-discovery/runs/{run_id}/finish",
        headers=DISCOVERY_HEADERS,
        json={
            "status": "succeeded",
            "discovered_raw_count": 10,
            "normalized_count": 9,
            "duplicate_count": 1,
            "new_candidate_count": 1,
            "adapter_stats": {"seed": 1, "bing": 9},
            "platform_stats": {"dujiao_next": 1},
            "failure_stats": {},
        },
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "succeeded"
    again = client.post(
        f"/api/v1/internal/source-discovery/runs/{run_id}/finish",
        headers=DISCOVERY_HEADERS,
        json={"status": "failed"},
    )
    assert again.status_code == 409
    rows = client.get("/api/v1/admin/source-discovery/runs", headers=ADMIN_HEADERS).json()
    assert len(rows) == 1
    assert rows[0]["trigger"] == "manual"
    assert rows[0]["adapter_stats"] == {"seed": 1, "bing": 9}
    detail = client.get(f"/api/v1/admin/source-discovery/runs/{run_id}", headers=ADMIN_HEADERS)
    assert detail.status_code == 200


def test_discovery_run_funnel_counts_follow_candidate_results(client, engine):
    run_id = client.post(
        "/api/v1/internal/source-discovery/runs",
        headers=DISCOVERY_HEADERS,
        json={"trigger": "manual", "adapters": ["bing"]},
    ).json()["run_id"]
    upsert(client, "https://funnel-one.example.com", hint="woocommerce", run_id=run_id)
    task = claim(client)[0]
    reported = report(client, task["candidate_id"], task["attempt_count"])
    assert reported.json()["status"] == "promoted"
    with Session(engine) as db:
        candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == task["candidate_id"]))
        assert candidate.discovery_run_id == run_id
    run = client.get(f"/api/v1/admin/source-discovery/runs/{run_id}", headers=ADMIN_HEADERS).json()
    assert run["detected_count"] == 1
    assert run["ai_matched_count"] == 1
    assert run["auto_approved_count"] == 1
    assert run["promoted_intake_count"] == 1
    assert run["platform_stats"] == {"woocommerce": 1}


def test_discovery_run_validation_failure_is_counted(client, engine):
    run_id = client.post(
        "/api/v1/internal/source-discovery/runs",
        headers=DISCOVERY_HEADERS,
        json={"trigger": "manual", "adapters": ["seed"]},
    ).json()["run_id"]
    upsert(client, "https://funnel-fail.example.com", hint="dujiao_next", run_id=run_id)
    task = claim(client)[0]
    report(
        client,
        task["candidate_id"],
        task["attempt_count"],
        status="validation_failed",
        failure_reason="timeout",
    )
    run = client.get(f"/api/v1/admin/source-discovery/runs/{run_id}", headers=ADMIN_HEADERS).json()
    assert run["validation_failed_count"] == 1
    assert run["failure_stats"] == {"timeout": 1}
    assert run["detected_count"] == 0


def test_recovery_task_repromotes_orphaned_candidates(client, engine):
    upsert(client, "https://orphan.example.com", hint="woocommerce")
    task = claim(client)[0]
    report(client, task["candidate_id"], task["attempt_count"])
    with Session(engine) as db:
        candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == task["candidate_id"]))
        candidate.status = "auto_approved"
        candidate.promoted_intake_id = None
        db.commit()
    recovered = client.post(
        "/api/v1/admin/source-candidates/recover",
        headers=ADMIN_HEADERS,
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovered"] == 1
    with Session(engine) as db:
        candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == task["candidate_id"]))
        assert candidate.status == "promoted"
        assert candidate.promoted_intake_id is not None
        intake = db.scalar(select(SourceIntake).where(SourceIntake.id == candidate.promoted_intake_id))
        assert intake.status == "approved"


def test_discovery_run_must_exist_and_be_running_for_upsert(client):
    missing_run = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers=DISCOVERY_HEADERS,
        json={
            "run_id": 999999,
            "discovered_url": "https://missing.example.com",
            "discovered_by": "seed",
        },
    )
    assert missing_run.status_code == 404
    finished = client.post(
        "/api/v1/internal/source-discovery/runs",
        headers=DISCOVERY_HEADERS,
        json={"trigger": "manual", "adapters": ["seed"]},
    ).json()
    run_id = finished["run_id"]
    client.post(
        f"/api/v1/internal/source-discovery/runs/{run_id}/finish",
        headers=DISCOVERY_HEADERS,
        json={"status": "succeeded"},
    )
    blocked = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers=DISCOVERY_HEADERS,
        json={
            "run_id": run_id,
            "discovered_url": "https://blocked.example.com",
            "discovered_by": "seed",
        },
    )
    assert blocked.status_code == 409


def test_large_payload_is_rejected(client):
    huge_url = "https://example.com/" + "a" * (1024 * 1024)
    response = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers=DISCOVERY_HEADERS,
        json={"discovered_url": huge_url, "discovered_by": "seed"},
    )
    assert response.status_code == 413


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_concurrent_upsert_on_postgres_merges_into_one_candidate():
    import threading

    from sqlalchemy import create_engine as pg_create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = os.environ["TEST_POSTGRES_URL"]
    engine = pg_create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    errors: list[BaseException] = []

    def worker(source: str) -> None:
        try:
            with session_factory() as db:
                upsert_candidate = __import__("app.services.source_discovery", fromlist=["upsert_candidate"]).upsert_candidate
                result = upsert_candidate(
                    db,
                    discovered_url="https://concurrent.example.com/products/chatgpt",
                    platform_hint="dujiao_next",
                    discovered_by=source,
                    matched_query=f"query-{source}",
                )
                db.commit()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"source-{index}",)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors
    with session_factory() as db:
        candidates = list(db.scalars(select(SourceCandidate)))
        assert len(candidates) == 1
        assert candidates[0].candidate_key == "https://concurrent.example.com"
        assert len(candidates[0].discovery_sources) == 4
