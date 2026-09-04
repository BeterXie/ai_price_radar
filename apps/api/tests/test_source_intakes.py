from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import NotificationOutbox, Report, Shop, SourceIntake
from app.services import outbox
from app.services.outbox import process_once


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def api_client(monkeypatch):
    engine = _engine()
    Base.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")
    monkeypatch.setattr(settings, "intake_worker_key", "worker-test")
    monkeypatch.setattr(settings, "detector_worker_key", "detector-test")
    monkeypatch.setattr(settings, "report_rate_limit_count", 100)
    monkeypatch.setattr(settings, "public_site_url", "https://ai.pricememo.cn")

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.clear()


def _payload(token: str = "ABC123", **extra):
    return {
        "shop_url": f"https://pay.ldxp.cn/shop/{token}",
        "shop_name": "测试店铺",
        "contact": "merchant@example.com",
        "note": "公开 AI 商品申请",
        **extra,
    }


def _detect(client: TestClient, intake_id: int, *, platform: str = "ldxp", source_url: str = "", source_key: str = ""):
    headers = {"X-Detector-Worker-Key": "detector-test"}
    claimed = client.post(
        "/api/v1/internal/source-detections/claim",
        headers=headers,
        json={"limit": 1, "lease_seconds": 300},
    )
    assert claimed.status_code == 200
    task = claimed.json()[0]
    assert task["intake_id"] == intake_id
    if not source_url:
        source_url = task["source_url"]
    if not source_key:
        source_key = source_url.rsplit("/", 1)[-1].casefold() if platform == "ldxp" else source_url
    result = client.post(
        f"/api/v1/internal/source-detections/{intake_id}/result",
        headers=headers,
        json={
            "status": "pending_review",
            "attempt_count": task["attempt_count"],
            "detected_platform": platform,
            "source_url": source_url,
            "source_key": source_key,
            "product_count": 1,
        },
    )
    assert result.status_code == 200
    return result


def test_shop_request_requires_valid_contact_email(api_client):
    client, _ = api_client
    missing = client.post("/api/v1/shop-requests", json={"shop_url": "https://pay.ldxp.cn/shop/ABC123"})
    invalid = client.post(
        "/api/v1/shop-requests",
        json={"shop_url": "https://pay.ldxp.cn/shop/ABC123", "contact": "微信号"},
    )
    assert missing.status_code == 422
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    ("platform", "source_url"),
    [
        ("woocommerce", "https://woocommerce.example/products/example"),
        ("schema_org", "https://schema-org.example/products/example"),
        ("16688", "https://www.16688.com.cn/shop/S343514"),
    ],
)
def test_structured_platform_submission_can_be_detected_and_reviewed(api_client, platform, source_url):
    client, engine = api_client
    response = client.post(
        "/api/v1/shop-requests",
        json={
            **_payload(),
            "shop_url": source_url,
            "source_type": platform,
        },
    )
    assert response.status_code == 201
    intake_id = response.json()["request_id"]

    _detect(client, intake_id, platform=platform, source_url=source_url, source_key=source_url)

    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert (intake.source_type, intake.detected_platform, intake.status) == (
            platform,
            platform,
            "pending_review",
        )
        assert intake.source_url == source_url


def test_16688_submission_uses_platform_scoped_alias_token(api_client):
    client, _ = api_client
    response = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "source_type": "16688", "shop_url": "https://www.16688.com.cn/shop/HARVEY"},
    )
    assert response.status_code == 201
    assert response.json()["shop_token"] == "16688-HARVEY"


def test_submission_is_an_intake_and_outbox_is_transactional(api_client):
    client, engine = api_client
    created = client.post("/api/v1/shop-requests", json=_payload())
    assert created.status_code == 201
    intake_id = created.json()["request_id"]

    duplicate = client.post("/api/v1/shop-requests", json=_payload("abc123"))
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "already_pending"
    assert duplicate.json()["request_id"] == intake_id

    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert intake is not None
        assert intake.source_key == "abc123"
        assert intake.declared_platform == "auto"
        assert intake.source_type == "unknown"
        assert intake.detected_platform == "unknown"
        assert intake.status == "submitted"
        outbox = list(db.scalars(select(NotificationOutbox).order_by(NotificationOutbox.id)))
        assert len(outbox) == 2
        assert {row.event_type for row in outbox} == {
            "shop_request.submitted.admin",
            "shop_request.submitted.applicant",
        }
        admin_mail = next(row for row in outbox if row.event_type == "shop_request.submitted.admin")
        assert f"https://ai.pricememo.cn/admin?intake={intake_id}#source-intake-{intake_id}" in admin_mail.text_body
        assert "输入管理密钥" in admin_mail.text_body


def test_public_submission_never_resolves_or_fetches_user_url(api_client, monkeypatch):
    client, engine = api_client
    monkeypatch.setattr(
        "app.services.source_platform.socket.getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("public API must not resolve source hosts")),
    )
    monkeypatch.setattr(
        "app.services.source_platform._fetch_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("public API must not fetch source URLs")),
    )
    response = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://untrusted.example/catalog.json"},
    )
    assert response.status_code == 201
    assert response.json()["workflow_status"] == "submitted"
    with Session(engine) as db:
        intake = db.get(SourceIntake, response.json()["request_id"])
        assert (intake.source_type, intake.detected_platform, intake.status) == ("unknown", "unknown", "submitted")


def test_detector_key_lease_recovery_and_failure_sanitization(api_client):
    client, engine = api_client
    intake_id = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://untrusted.example/catalog.json"},
    ).json()["request_id"]
    detector_headers = {"X-Detector-Worker-Key": "detector-test"}

    unauthorized = client.post(
        "/api/v1/internal/source-detections/claim",
        headers={"X-Intake-Worker-Key": "worker-test"},
        json={"limit": 1, "lease_seconds": 300},
    )
    assert unauthorized.status_code == 401

    first_claim = client.post(
        "/api/v1/internal/source-detections/claim",
        headers=detector_headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        intake.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    second_claim = client.post(
        "/api/v1/internal/source-detections/claim",
        headers=detector_headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    assert first_claim["attempt_count"] == 1
    assert second_claim["attempt_count"] == 2

    stale = client.post(
        f"/api/v1/internal/source-detections/{intake_id}/result",
        headers=detector_headers,
        json={"status": "validation_failed", "attempt_count": 1, "failure_reason": "secret=stale"},
    )
    assert stale.status_code == 409
    current = client.post(
        f"/api/v1/internal/source-detections/{intake_id}/result",
        headers=detector_headers,
        json={"status": "validation_failed", "attempt_count": 2, "failure_reason": "secret=current"},
    )
    assert current.status_code == 200
    assert current.json()["status"] == "validation_failed"
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert intake.source_type == "unknown"
        assert intake.status == "validation_failed"
        assert intake.failure_reason == "来源安全检测失败"
        assert "secret" not in intake.failure_reason
        assert intake.lease_expires_at is None
        assert intake.finished_at is not None


def test_legacy_merchant_feed_input_is_canonicalized_without_persisting_alias(api_client):
    client, engine = api_client
    url = "https://feed.example/catalog.json"
    response = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "source_type": "merchant_feed", "shop_url": url},
    )
    assert response.status_code == 201
    assert response.json()["declared_platform"] == "merchant_json"
    with Session(engine) as db:
        intake = db.scalar(select(SourceIntake).where(SourceIntake.source_key == url))
        assert intake is not None
        assert intake.source_type == "unknown"
        assert intake.declared_platform == "merchant_json"


def test_detection_merges_two_product_pages_into_one_canonical_dujiao_source(api_client):
    client, engine = api_client
    first = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://shop.example/products/a", "note": "first note"},
    ).json()["request_id"]
    second = client.post(
        "/api/v1/shop-requests",
        json={
            **_payload(),
            "shop_url": "https://shop.example/products/b",
            "contact": "second@example.com",
            "note": "second note",
        },
    ).json()["request_id"]
    headers = {"X-Detector-Worker-Key": "detector-test"}
    claims = client.post(
        "/api/v1/internal/source-detections/claim",
        headers=headers,
        json={"limit": 2, "lease_seconds": 300},
    ).json()
    assert {task["intake_id"] for task in claims} == {first, second}
    attempts = {task["intake_id"]: task["attempt_count"] for task in claims}

    for intake_id in (first, second):
        response = client.post(
            f"/api/v1/internal/source-detections/{intake_id}/result",
            headers=headers,
            json={
                "status": "pending_review",
                "attempt_count": attempts[intake_id],
                "detected_platform": "dujiao_next",
                "source_url": "https://shop.example",
                "source_key": "https://shop.example/",
                "shop_name": "Canonical Shop",
                "product_count": intake_id,
            },
        )
        assert response.status_code == 200

    with Session(engine) as db:
        rows = list(db.scalars(select(SourceIntake)))
        assert len(rows) == 1
        intake = rows[0]
        assert (intake.source_type, intake.source_key, intake.status) == (
            "dujiao_next",
            "https://shop.example/",
            "pending_review",
        )
        assert "first note" in intake.note and "second note" in intake.note
        assert "second@example.com" in intake.note


def test_detection_merges_resubmission_into_published_source_without_downgrade(api_client):
    client, engine = api_client
    with Session(engine) as db:
        db.add(SourceIntake(
            source_type="dujiao_next",
            declared_platform="dujiao_next",
            detected_platform="dujiao_next",
            source_key="https://shop.example/",
            source_url="https://shop.example/",
            contact_email="owner@example.com",
            status="published",
            product_count=3,
        ))
        db.commit()
    duplicate_id = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://shop.example/products/new"},
    ).json()["request_id"]
    headers = {"X-Detector-Worker-Key": "detector-test"}
    task = client.post(
        "/api/v1/internal/source-detections/claim",
        headers=headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    response = client.post(
        f"/api/v1/internal/source-detections/{duplicate_id}/result",
        headers=headers,
        json={
            "status": "pending_review",
            "attempt_count": task["attempt_count"],
            "detected_platform": "dujiao_next",
            "source_url": "https://shop.example",
            "source_key": "https://shop.example/",
            "product_count": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    with Session(engine) as db:
        rows = list(db.scalars(select(SourceIntake)))
        assert len(rows) == 1
        assert rows[0].status == "published"
        assert rows[0].product_count == 3


def test_approve_validate_publish_is_idempotent_and_requires_published_sync(api_client):
    client, engine = api_client
    created = client.post("/api/v1/shop-requests", json=_payload("APPROVE1"))
    intake_id = created.json()["request_id"]
    _detect(client, intake_id)
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}

    approved = client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"
    assert approved.json()["workflow_status"] == "approved"
    repeated = client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers)
    assert repeated.status_code == 200

    with Session(engine) as db:
        approved_mail = db.scalar(select(NotificationOutbox).where(NotificationOutbox.event_type == "shop_request.approved"))
        assert approved_mail is not None
        assert "店铺地址：https://pay.ldxp.cn/shop/APPROVE1" in approved_mail.text_body
        assert "店铺名称：测试店铺" in approved_mail.text_body

    claimed = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1, "lease_seconds": 300},
    )
    assert claimed.status_code == 200
    claim_attempt = claimed.json()[0]["attempt_count"]
    assert claim_attempt == 2

    validated = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "validated", "attempt_count": claim_attempt, "product_count": 2},
    )
    assert validated.status_code == 200
    not_published = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": claim_attempt, "product_count": 2},
    )
    assert not_published.status_code == 409

    with Session(engine) as db:
        db.add(Shop(token="APPROVE1", name="测试店铺", source_url="https://pay.ldxp.cn/shop/APPROVE1"))
        db.commit()

    onboarded = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": claim_attempt, "product_count": 2, "published": True},
    )
    assert onboarded.status_code == 200
    assert onboarded.json()["status"] == "onboarded"
    assert onboarded.json()["workflow_status"] == "published"
    repeated_onboard = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": claim_attempt, "product_count": 2, "published": True},
    )
    assert repeated_onboard.status_code == 200
    stale_onboard = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": claim_attempt + 1, "product_count": 2, "published": True},
    )
    assert stale_onboard.status_code == 409
    with Session(engine) as db:
        events = list(db.scalars(select(NotificationOutbox)))
        assert len(events) == 4
        assert sum(row.event_type == "shop_intake.onboarded" for row in events) == 1
        onboarded_mail = next(row for row in events if row.event_type == "shop_intake.onboarded")
        assert "店铺地址：https://pay.ldxp.cn/shop/APPROVE1" in onboarded_mail.text_body
        assert "店铺名称：测试店铺" in onboarded_mail.text_body
        assert "本站收录页面：https://ai.pricememo.cn/shops/APPROVE1" in onboarded_mail.text_body


def test_closed_intake_attempt_ignores_retried_scan_result(api_client):
    client, _ = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("RETRY1")).json()["request_id"]
    _detect(client, intake_id)
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}
    assert client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers).status_code == 200
    claim = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    attempt_count = claim["attempt_count"]
    validated = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "validated", "attempt_count": attempt_count, "product_count": 1},
    )
    assert validated.status_code == 200

    retried = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "no_products", "attempt_count": attempt_count, "product_count": 0},
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "validated"

    stale = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "no_products", "attempt_count": attempt_count + 1, "product_count": 0},
    )
    assert stale.status_code == 409


def test_declared_platform_mismatch_is_saved_and_reported(api_client, monkeypatch):
    client, engine = api_client
    response = client.post(
        "/api/v1/shop-requests",
        json={
            **_payload(),
            "source_type": "ldxp",
            "shop_url": "https://shop.example.com",
        },
    )
    assert response.status_code == 201
    assert response.json()["declared_platform"] == "ldxp"
    assert response.json()["detected_platform"] == "unknown"
    assert response.json()["workflow_status"] == "submitted"
    intake_id = response.json()["request_id"]
    detected = _detect(
        client,
        intake_id,
        platform="dujiao_next",
        source_url="https://shop.example.com",
        source_key="https://shop.example.com",
    )
    assert detected.json()["workflow_status"] == "pending_review"
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert intake.declared_platform == "ldxp"
        assert intake.detected_platform == "dujiao_next"


def test_non_ldxp_approval_routes_to_atomic_publisher_or_stays_manual(api_client):
    client, _ = api_client
    admin_headers = {"X-Admin-Key": "admin-test"}

    dujiao_id = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://dujiao.example", "source_type": "dujiao_next"},
    ).json()["request_id"]
    _detect(
        client,
        dujiao_id,
        platform="dujiao_next",
        source_url="https://dujiao.example",
        source_key="https://dujiao.example",
    )
    approved = client.post(f"/api/v1/admin/source-intakes/{dujiao_id}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    ldxp_claim = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers={"X-Intake-Worker-Key": "worker-test"},
        json={"limit": 10},
    )
    assert ldxp_claim.status_code == 200
    assert ldxp_claim.json() == []

    other_id = client.post(
        "/api/v1/shop-requests",
        json={**_payload("OTHER"), "shop_url": "https://other.example", "source_type": "other"},
    ).json()["request_id"]
    _detect(client, other_id, platform="other", source_url="https://other.example", source_key="https://other.example")
    blocked = client.post(f"/api/v1/admin/source-intakes/{other_id}/approve", headers=admin_headers)
    assert blocked.status_code == 409


def test_reject_retry_and_lease_generation_are_idempotent(api_client):
    client, engine = api_client
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}

    rejected_id = client.post("/api/v1/shop-requests", json=_payload("REJECT1")).json()["request_id"]
    _detect(client, rejected_id)
    rejected = client.post(
        f"/api/v1/admin/source-intakes/{rejected_id}/reject",
        headers=admin_headers,
        json={"reason": "来源信息不足"},
    )
    assert rejected.status_code == 200
    repeated_reject = client.post(
        f"/api/v1/admin/source-intakes/{rejected_id}/reject",
        headers=admin_headers,
        json={"reason": "其他原因"},
    )
    assert repeated_reject.status_code == 200

    intake_id = client.post("/api/v1/shop-requests", json=_payload("LEASE1")).json()["request_id"]
    _detect(client, intake_id)
    assert client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers).status_code == 200
    first_claim = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        intake.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    second_claim = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1, "lease_seconds": 300},
    ).json()[0]
    assert first_claim["attempt_count"] == 2
    assert second_claim["attempt_count"] == 3
    stale = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "validation_failed", "attempt_count": 2, "failure_reason": "旧任务"},
    )
    assert stale.status_code == 409
    current = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "no_products", "attempt_count": 3},
    )
    assert current.status_code == 200
    retried = client.post(f"/api/v1/admin/source-intakes/{intake_id}/retry", headers=admin_headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"
    repeated_retry = client.post(f"/api/v1/admin/source-intakes/{intake_id}/retry", headers=admin_headers)
    assert repeated_retry.status_code == 200
    with Session(engine) as db:
        assert sum(row.event_type == "shop_request.rejected" for row in db.scalars(select(NotificationOutbox))) == 1
        assert sum(row.event_type == "shop_intake.no_products" for row in db.scalars(select(NotificationOutbox))) == 1
        rejected_mail = next(row for row in db.scalars(select(NotificationOutbox)) if row.event_type == "shop_request.rejected")
        assert "店铺地址：https://pay.ldxp.cn/shop/REJECT1" in rejected_mail.text_body
        assert "店铺名称：测试店铺" in rejected_mail.text_body


def test_worker_key_is_separate_and_pending_result_is_rejected(api_client):
    client, _ = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("AUTH1")).json()["request_id"]
    wrong_admin = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers={"X-Admin-Key": "admin-test"},
        json={"limit": 1},
    )
    assert wrong_admin.status_code == 401
    result = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers={"X-Intake-Worker-Key": "worker-test"},
        json={"status": "validated", "attempt_count": 1, "product_count": 1},
    )
    assert result.status_code == 409


def test_admin_can_requeue_a_failed_notification(api_client):
    client, engine = api_client
    with Session(engine) as db:
        row = NotificationOutbox(
            event_type="test.failed",
            recipient="user@example.com",
            subject="subject",
            text_body="body",
            status="failed",
            attempt_count=3,
            last_error="RuntimeError: SMTP delivery failed",
            dedupe_key="test-admin-retry",
        )
        db.add(row)
        db.commit()
        row_id = row.id
    response = client.post(
        f"/api/v1/admin/notification-outbox/{row_id}/retry",
        headers={"X-Admin-Key": "admin-test"},
    )
    assert response.status_code == 200
    with Session(engine) as db:
        row = db.get(NotificationOutbox, row_id)
        assert row.status == "pending"
        assert row.attempt_count == 0


def test_admin_can_requeue_failed_notifications_by_source_intake(api_client):
    client, engine = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("MAILRETRY")).json()["request_id"]
    with Session(engine) as db:
        db.add(NotificationOutbox(
            event_type="shop_intake.validation_failed",
            recipient="merchant@example.com",
            subject="subject",
            text_body="body",
            status="failed",
            attempt_count=4,
            last_error="RuntimeError: SMTP delivery failed",
            dedupe_key=f"source-intake:{intake_id}:shop_intake.validation_failed:attempt-1",
        ))
        db.commit()
    response = client.post(
        f"/api/v1/admin/source-intakes/{intake_id}/notifications/retry",
        headers={"X-Admin-Key": "admin-test"},
    )
    assert response.status_code == 200
    assert response.json()["email_status"]["shop_intake.validation_failed"] == "pending"
    with Session(engine) as db:
        row = db.scalar(select(NotificationOutbox).where(NotificationOutbox.event_type == "shop_intake.validation_failed"))
        assert row.status == "pending"
        assert row.attempt_count == 0


def test_admin_stats_separate_corrections_and_pending_intakes(api_client):
    client, engine = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("STAT1")).json()["request_id"]
    _detect(client, intake_id)
    with Session(engine) as db:
        db.add(Report(kind="correction", message="这是待处理的纠错信息", status="open"))
        db.commit()
    response = client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "admin-test"})
    assert response.status_code == 200
    stats = response.json()
    assert stats["open_corrections"] == 1
    assert stats["pending_source_intakes"] == 1
    assert stats["open_reports"] == 1


def test_internal_validation_failure_does_not_store_raw_error_details(api_client):
    client, engine = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("SANITIZE1")).json()["request_id"]
    _detect(client, intake_id)
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}
    client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers)
    claim = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1},
    ).json()[0]
    raw_error = "https://private.example/item?password=super-secret"
    response = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={
            "status": "validation_failed",
            "attempt_count": claim["attempt_count"],
            "failure_reason": raw_error,
        },
    )
    assert response.status_code == 200
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        mail = db.scalar(select(NotificationOutbox).where(NotificationOutbox.event_type == "shop_intake.validation_failed"))
        assert intake.failure_reason == "来源验证暂时失败"
        assert "super-secret" not in intake.failure_reason
        assert "private.example" not in mail.text_body


def test_outbox_worker_success_failure_backoff_and_secret_scrubbing(monkeypatch, caplog):
    engine = _engine()
    Base.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@example.com")
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    with Session(engine) as db:
        db.add(NotificationOutbox(
            event_type="test.success",
            recipient="user@example.com",
            subject="subject",
            text_body="body",
            dedupe_key="test-success",
            next_attempt_at=now,
        ))
        db.add(NotificationOutbox(
            event_type="test.failure",
            recipient="user@example.com",
            subject="subject",
            text_body="body",
            dedupe_key="test-failure",
            next_attempt_at=now,
        ))
        db.commit()

    sent: list[int] = []

    def send_success(row):
        if row.event_type == "test.failure":
            raise RuntimeError("smtp-password=super-secret")
        sent.append(row.id)

    first_failure_at = now
    with Session(engine) as db:
        assert process_once(db, send=send_success, now=now) == 1
        success = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-success"))
        assert success.status == "sent"
        failed = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-failure"))
        assert failed.attempt_count == 1
        assert failed.status == "pending"
        assert failed.next_attempt_at.replace(tzinfo=timezone.utc) == first_failure_at + timedelta(minutes=1)

    second_failure_at = now + timedelta(minutes=1)
    with Session(engine) as db:
        process_once(db, send=send_success, now=second_failure_at)
        failed = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-failure"))
        assert failed.attempt_count == 2
        assert failed.status == "pending"
        assert failed.next_attempt_at.replace(tzinfo=timezone.utc) == now + timedelta(minutes=6)

    third_failure_at = now + timedelta(minutes=6)
    with Session(engine) as db:
        process_once(db, send=send_success, now=third_failure_at)
        failed = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-failure"))
        assert failed.attempt_count == 3
        assert failed.status == "pending"
        assert failed.next_attempt_at.replace(tzinfo=timezone.utc) == now + timedelta(minutes=36)

    fourth_failure_at = now + timedelta(minutes=36)
    with Session(engine) as db:
        process_once(db, send=send_success, now=fourth_failure_at)
        failed = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-failure"))
        assert failed.attempt_count == 4
        assert failed.status == "failed"
        assert failed.next_attempt_at.replace(tzinfo=timezone.utc) == fourth_failure_at
        assert "super-secret" not in failed.last_error
        assert failed.last_error == "RuntimeError: mail delivery failed"
    assert "super-secret" not in caplog.text


def test_outbox_worker_keeps_mail_pending_without_smtp(monkeypatch):
    engine = _engine()
    Base.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "resend_from", "")
    with Session(engine) as db:
        db.add(NotificationOutbox(
            event_type="test.pending",
            recipient="user@example.com",
            subject="subject",
            text_body="body",
            dedupe_key="test-pending-no-smtp",
        ))
        db.commit()
        assert process_once(db) == 0
        row = db.scalar(select(NotificationOutbox).where(NotificationOutbox.dedupe_key == "test-pending-no-smtp"))
        assert row.status == "pending"


def test_resend_api_is_preferred_when_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_from", "notice@example.com")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "smtp@example.com")
    sent: list[dict[str, str]] = []

    monkeypatch.setattr(
        outbox.resend.Emails,
        "send",
        lambda payload: sent.append(payload) or {"id": "email_test"},
    )
    row = NotificationOutbox(
        event_type="test.resend",
        recipient="recipient@example.com",
        subject="Resend test",
        text_body="message body",
        dedupe_key="test-resend",
    )
    outbox.send_notification_message(row, settings)

    assert sent == [{
        "from": "notice@example.com",
        "to": "recipient@example.com",
        "subject": "Resend test",
        "text": "message body",
    }]


def test_admin_approve_other_intake_auto_upgrades_to_ldxp(api_client):
    client, engine = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("5FEQFLQO", shop_url="https://wzyp.cn/shop/5FEQFLQO")).json()["request_id"]
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        intake.status = "pending_review"
        intake.source_type = "other"
        intake.detected_platform = "other"
        db.commit()

    res = client.post(
        f"/api/v1/admin/source-intakes/{intake_id}/approve",
        headers={"X-Admin-Key": "admin-test"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["source_type"] == "ldxp"
    assert data["status"] == "queued"
    assert data["source_url"] == "https://wzyp.cn/shop/5FEQFLQO"
    assert data["source_key"] == "5feqflqo"


def test_admin_change_platform_and_redetect(api_client):
    client, engine = api_client
    intake_id = client.post("/api/v1/shop-requests", json=_payload("5FEQFLQO", shop_url="https://wzyp.cn/shop/5FEQFLQO")).json()["request_id"]
    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        intake.status = "pending_review"
        intake.source_type = "other"
        db.commit()

    res = client.post(
        f"/api/v1/admin/source-intakes/{intake_id}/platform",
        headers={"X-Admin-Key": "admin-test"},
        json={"platform": "dujiao_next"},
    )
    assert res.status_code == 200
    assert res.json()["source_type"] == "dujiao_next"

    res = client.post(
        f"/api/v1/admin/source-intakes/{intake_id}/redetect",
        headers={"X-Admin-Key": "admin-test"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "submitted"
    assert res.json()["source_type"] == "unknown"


def test_shop_intake_auto_approve_when_enabled(api_client, monkeypatch):
    client, engine = api_client
    settings = get_settings()
    monkeypatch.setattr(settings, "shop_intake_auto_approve", True)
    monkeypatch.setattr(settings, "shop_intake_admin_emails", "admin@example.com")

    # 1. ldxp auto-approves to queued
    intake_id = client.post("/api/v1/shop-requests", json=_payload("AUTO1")).json()["request_id"]
    detected = _detect(client, intake_id, platform="ldxp")
    assert detected.json()["status"] == "queued"
    assert detected.json()["workflow_status"] == "approved"

    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert intake.status == "queued"
        assert intake.approved_at is not None
        assert "已自动通过初审" in intake.decision_note

        # Verify notifications
        admin_notice = db.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "shop_request.auto_approved.admin",
                NotificationOutbox.recipient == "admin@example.com",
            )
        )
        assert admin_notice is not None
        assert "自动审批通过" in admin_notice.subject

        applicant_notice = db.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "shop_request.approved",
                NotificationOutbox.recipient == intake.contact_email,
            )
        )
        assert applicant_notice is not None
        assert "已自动通过初审" in applicant_notice.subject
        assert f"店铺地址：{intake.source_url}" in applicant_notice.text_body
        assert f"店铺名称：{intake.shop_name}" in applicant_notice.text_body

    # 2. dujiao_next auto-approves to approved
    intake_id_dj = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://dj.example.com", "source_type": "dujiao_next"},
    ).json()["request_id"]
    detected_dj = _detect(
        client,
        intake_id_dj,
        platform="dujiao_next",
        source_url="https://dj.example.com",
        source_key="https://dj.example.com",
    )
    assert detected_dj.json()["status"] == "approved"
    assert detected_dj.json()["workflow_status"] == "approved"


def test_shop_intake_auto_approve_ignores_other(api_client, monkeypatch):
    client, engine = api_client
    settings = get_settings()
    monkeypatch.setattr(settings, "shop_intake_auto_approve", True)

    intake_id = client.post(
        "/api/v1/shop-requests",
        json={**_payload(), "shop_url": "https://custom.example.com"},
    ).json()["request_id"]
    detected = _detect(
        client,
        intake_id,
        platform="other",
        source_url="https://custom.example.com",
        source_key="https://custom.example.com",
    )
    assert detected.json()["status"] == "pending_review"


def test_injection_crlf_in_shop_name_is_sanitized(api_client, monkeypatch):
    client, engine = api_client
    settings = get_settings()
    monkeypatch.setattr(settings, "shop_intake_auto_approve", True)
    monkeypatch.setattr(settings, "shop_intake_admin_emails", "admin@example.com")

    # Attempt header injection via shop_name
    malicious_name = "EvilStore\r\nBcc: evil@attacker.com\r\nSubject: InjectedHeader"
    res = client.post(
        "/api/v1/shop-requests",
        json=_payload("INJECT1", shop_name=malicious_name),
    )
    assert res.status_code == 201
    intake_id = res.json()["request_id"]

    _detect(client, intake_id, platform="ldxp")

    with Session(engine) as db:
        intake = db.get(SourceIntake, intake_id)
        assert "\r" not in intake.shop_name
        assert "\n" not in intake.shop_name

        # Verify all outbox messages have safe headers without any CRLF
        for row in db.scalars(select(NotificationOutbox)).all():
            assert "\r" not in row.subject
            assert "\n" not in row.subject
            assert "\r" not in row.recipient
            assert "\n" not in row.recipient


def test_injection_crlf_in_contact_is_rejected(api_client):
    client, _ = api_client
    # Attempt CRLF in contact email
    res = client.post(
        "/api/v1/shop-requests",
        json=_payload("INJECT2", contact="victim@example.com\r\nBcc: evil@attacker.com"),
    )
    assert res.status_code == 422

    # Attempt comma-separated multiple recipients
    res2 = client.post(
        "/api/v1/shop-requests",
        json=_payload("INJECT3", contact="victim@example.com, evil@attacker.com"),
    )
    assert res2.status_code == 422

    # Attempt angle brackets / XSS
    res3 = client.post(
        "/api/v1/shop-requests",
        json=_payload("INJECT4", contact="<script>alert(1)</script>@example.com"),
    )
    assert res3.status_code == 422


def test_injection_ssrf_urls_rejected(api_client):
    client, _ = api_client
    ssrf_urls = [
        "https://127.0.0.1/shop",
        "https://localhost:8000/shop",
        "https://169.254.169.254/latest/meta-data",
        "https://internal.lan/shop",
        "https://router.local/shop",
        "https://192.168.1.1/shop",
        "https://10.0.0.1/shop",
    ]
    for url in ssrf_urls:
        res = client.post(
            "/api/v1/shop-requests",
            json=_payload("SSRF", shop_url=url),
        )
        assert res.status_code == 422, f"Expected 422 for {url}, got {res.status_code}"



