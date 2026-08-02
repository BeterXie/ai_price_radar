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
from app.models import NotificationOutbox, Report, SourceIntake
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
    monkeypatch.setattr(settings, "report_rate_limit_count", 100)

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


def test_shop_request_requires_valid_contact_email(api_client):
    client, _ = api_client
    missing = client.post("/api/v1/shop-requests", json={"shop_url": "https://pay.ldxp.cn/shop/ABC123"})
    invalid = client.post(
        "/api/v1/shop-requests",
        json={"shop_url": "https://pay.ldxp.cn/shop/ABC123", "contact": "微信号"},
    )
    assert missing.status_code == 422
    assert invalid.status_code == 422


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
        assert intake.status == "pending_review"
        outbox = list(db.scalars(select(NotificationOutbox).order_by(NotificationOutbox.id)))
        assert len(outbox) == 2
        assert {row.event_type for row in outbox} == {
            "shop_request.submitted.admin",
            "shop_request.submitted.applicant",
        }


def test_approve_validate_publish_is_idempotent_and_requires_published_sync(api_client):
    client, engine = api_client
    created = client.post("/api/v1/shop-requests", json=_payload("APPROVE1"))
    intake_id = created.json()["request_id"]
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}

    approved = client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"
    repeated = client.post(f"/api/v1/admin/source-intakes/{intake_id}/approve", headers=admin_headers)
    assert repeated.status_code == 200

    with Session(engine) as db:
        assert db.scalar(select(NotificationOutbox).where(NotificationOutbox.event_type == "shop_request.approved")) is not None
        assert db.scalar(select(NotificationOutbox.id).where(NotificationOutbox.event_type == "shop_request.approved")) is not None

    claimed = client.post(
        "/api/v1/internal/source-intakes/claim",
        headers=worker_headers,
        json={"limit": 1, "lease_seconds": 300},
    )
    assert claimed.status_code == 200
    assert claimed.json()[0]["attempt_count"] == 1

    validated = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "validated", "attempt_count": 1, "product_count": 2},
    )
    assert validated.status_code == 200
    not_published = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": 1, "product_count": 2},
    )
    assert not_published.status_code == 409

    onboarded = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": 1, "product_count": 2, "published": True},
    )
    assert onboarded.status_code == 200
    assert onboarded.json()["status"] == "onboarded"
    repeated_onboard = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "onboarded", "attempt_count": 1, "product_count": 2, "published": True},
    )
    assert repeated_onboard.status_code == 200

    with Session(engine) as db:
        events = list(db.scalars(select(NotificationOutbox)))
        assert len(events) == 4
        assert sum(row.event_type == "shop_intake.onboarded" for row in events) == 1


def test_reject_retry_and_lease_generation_are_idempotent(api_client):
    client, engine = api_client
    admin_headers = {"X-Admin-Key": "admin-test"}
    worker_headers = {"X-Intake-Worker-Key": "worker-test"}

    rejected_id = client.post("/api/v1/shop-requests", json=_payload("REJECT1")).json()["request_id"]
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
    assert first_claim["attempt_count"] == 1
    assert second_claim["attempt_count"] == 2
    stale = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "validation_failed", "attempt_count": 1, "failure_reason": "旧任务"},
    )
    assert stale.status_code == 409
    current = client.post(
        f"/api/v1/internal/source-intakes/{intake_id}/result",
        headers=worker_headers,
        json={"status": "no_products", "attempt_count": 2},
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
    client.post("/api/v1/shop-requests", json=_payload("STAT1"))
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
