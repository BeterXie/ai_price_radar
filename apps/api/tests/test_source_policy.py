from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import Base as ApiBase, get_db
from app.main import app
from app.models import SourceIntake, SourcePolicyRequest
from app.services.source_policy import source_identity


def _client(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "policy.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-policy")
    monkeypatch.setattr(settings, "discovery_worker_key", "discovery-policy")

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.state.test_policy_engine = engine
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_opt_out_request_creates_immediate_legal_hold(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "opt_out",
                "requester_email": "owner@example.com",
                "reason": "please remove my shop",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "pending_unverified"
        assert body["temporary_hold_at"] is not None

        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        )
        assert check.status_code == 200
        assert check.json()["source_status"] == "legal_hold"
        assert check.json()["allowed"] is False

        unauthorized = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
        )
        assert unauthorized.status_code == 401


def test_admin_applied_decision_disables_matching_ldxp_intake(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        engine = test_client.app.state.test_policy_engine
        with Session(engine) as db:
            db.add(SourceIntake(
                source_type="ldxp",
                declared_platform="ldxp",
                detected_platform="ldxp",
                source_key="https://pay.ldxp.cn/shop/TEST01",
                source_url="https://pay.ldxp.cn/shop/TEST01",
                contact_email="applicant@example.com",
                status="queued",
                origin="manual",
            ))
            db.add(SourceIntake(
                source_type="ldxp",
                declared_platform="ldxp",
                detected_platform="ldxp",
                source_key="https://pay.ldxp.cn/shop/OTHER02",
                source_url="https://pay.ldxp.cn/shop/OTHER02",
                contact_email="applicant@example.com",
                status="queued",
                origin="manual",
            ))
            db.commit()

        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "opt_out",
                "requester_email": "owner@example.com",
                "reason": "opt out",
            },
        ).json()
        request_id = created["id"]
        decided = test_client.post(
            f"/api/v1/admin/source-policy/requests/{request_id}/decide",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "owner verified"},
        )
        assert decided.status_code == 200
        assert decided.json()["status"] == "applied"
        with Session(engine) as db:
            intakes = list(db.scalars(select(SourceIntake)))
            by_url = {intake.source_url: intake for intake in intakes}
            assert by_url["https://pay.ldxp.cn/shop/TEST01"].status == "disabled"
            assert by_url["https://pay.ldxp.cn/shop/OTHER02"].status == "queued"

        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "opted_out"
        assert check["allowed"] is False


def test_emergency_stop_and_resume(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        stopped = test_client.post(
            "/api/v1/admin/source-policy/emergency-stop",
            headers={"X-Admin-Key": "admin-policy"},
            json={"reason": "legal review"},
        )
        assert stopped.status_code == 200
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["emergency_stopped"] is True
        assert check["allowed"] is False

        resumed = test_client.post(
            "/api/v1/admin/source-policy/resume",
            headers={"X-Admin-Key": "admin-policy"},
            json={"reason": "review complete"},
        )
        assert resumed.status_code == 200
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["emergency_stopped"] is False
        assert check["allowed"] is True


def test_admin_policy_requests_listing(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "correction",
                "requester_email": "owner@example.com",
                "reason": "price outdated",
            },
        )
        rows = test_client.get(
            "/api/v1/admin/source-policy/requests",
            headers={"X-Admin-Key": "admin-policy"},
        )
        assert rows.status_code == 200
        assert len(rows.json()) == 1
        assert rows.json()[0]["request_type"] == "correction"


def test_correction_and_ownership_do_not_freeze_source(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "correction",
                "requester_email": "owner@example.com",
                "reason": "price outdated",
            },
        )
        assert created.status_code == 201
        assert created.json()["temporary_hold_at"] is None
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "active"
        assert check["allowed"] is True


def test_applied_correction_does_not_disable_intake(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        engine = test_client.app.state.test_policy_engine
        with Session(engine) as db:
            db.add(SourceIntake(
                source_type="ldxp",
                source_key="https://pay.ldxp.cn/shop/TEST01",
                source_url="https://pay.ldxp.cn/shop/TEST01",
                contact_email="applicant@example.com",
                status="queued",
                origin="manual",
            ))
            db.commit()
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "correction",
                "requester_email": "owner@example.com",
                "reason": "price outdated",
            },
        ).json()
        decided = test_client.post(
            f"/api/v1/admin/source-policy/requests/{created['id']}/decide",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "fixed"},
        )
        assert decided.status_code == 200
        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/TEST01"))
            assert intake.status == "queued"


def test_applied_opt_out_is_sticky_and_reverse_restores(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        engine = test_client.app.state.test_policy_engine
        with Session(engine) as db:
            db.add(SourceIntake(
                source_type="ldxp",
                source_key="https://pay.ldxp.cn/shop/STICKY",
                source_url="https://pay.ldxp.cn/shop/STICKY",
                contact_email="applicant@example.com",
                status="approved",
                origin="manual",
            ))
            db.commit()
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/STICKY",
                "request_type": "opt_out",
                "requester_email": "owner@example.com",
                "reason": "opt out",
            },
        ).json()
        applied = test_client.post(
            f"/api/v1/admin/source-policy/requests/{created['id']}/decide",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "verified"},
        )
        assert applied.status_code == 200

        # A later rejected request must not override the applied opt-out.
        late = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/STICKY",
                "request_type": "opt_out",
                "requester_email": "other@example.com",
                "reason": "cancel my request",
            },
        )
        assert late.status_code == 422  # duplicate active opt-out rejected
        assert "already exists" in late.json()["detail"]
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/STICKY"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "opted_out"

        reversed_request = test_client.post(
            f"/api/v1/admin/source-policy/requests/{created['id']}/reverse",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "owner confirmed"},
        )
        assert reversed_request.status_code == 200
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/STICKY"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "active"
        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/STICKY"))
            assert intake.status == "approved"


def test_policy_request_validation_and_rate_limits(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        bad_email = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/TEST01",
                "request_type": "opt_out",
                "requester_email": "not-an-email",
                "reason": "",
            },
        )
        assert bad_email.status_code == 422
        payload = {
            "source_url": "https://pay.ldxp.cn/shop/LIMIT",
            "request_type": "correction",
            "requester_email": "owner@example.com",
            "reason": "issue",
        }
        for _index in range(3):
            response = test_client.post("/api/v1/source-policy/requests", json=payload)
            assert response.status_code == 201
        too_many = test_client.post("/api/v1/source-policy/requests", json=payload)
        assert too_many.status_code == 422
        assert "too many" in too_many.json()["detail"]


def test_source_identity_requires_official_ldxp_host_for_token_matching():
    assert source_identity("https://pay.ldxp.cn/shop/TEST01") == ("ldxp", "test01")
    assert source_identity("https://www.ldxp.cn/shop/TEST01") == ("ldxp", "test01")
    assert source_identity("https://ldxp.cn/shop/TEST01") == ("ldxp", "test01")
    assert source_identity("https://attacker.example/shop/TEST01") == ("url", "https://attacker.example/shop/TEST01")
    assert source_identity("https://pay.ldxp.cn/shop/bad token") == ("url", "https://pay.ldxp.cn/shop/bad token")


def test_cross_domain_opt_out_cannot_freeze_ldxp_shop(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://attacker.example/shop/TEST01",
                "request_type": "opt_out",
                "requester_email": "attacker@example.com",
                "reason": "look-alike",
            },
        )
        assert created.status_code == 201
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/TEST01"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "active"
        assert check["allowed"] is True


def test_unverified_hold_expires_after_24_hours(tmp_path, monkeypatch):
    from datetime import timedelta

    from app.services.source_intake import utcnow

    for test_client in _client(tmp_path, monkeypatch):
        engine = test_client.app.state.test_policy_engine
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/EXPIRE",
                "request_type": "opt_out",
                "requester_email": "owner@example.com",
                "reason": "opt out",
            },
        ).json()
        assert created["status"] == "pending_unverified"
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/EXPIRE"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "legal_hold"

        with Session(engine) as db:
            request = db.get(SourcePolicyRequest, created["id"])
            request.temporary_hold_at = utcnow() - timedelta(hours=25)
            db.commit()
        check = test_client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://pay.ldxp.cn/shop/EXPIRE"},
            headers={"X-Discovery-Worker-Key": "discovery-policy"},
        ).json()
        assert check["source_status"] == "active"
        assert check["allowed"] is True


def test_reverse_restores_only_effects_of_that_opt_out(tmp_path, monkeypatch):
    for test_client in _client(tmp_path, monkeypatch):
        engine = test_client.app.state.test_policy_engine
        with Session(engine) as db:
            db.add(SourceIntake(
                source_type="ldxp",
                source_key="https://pay.ldxp.cn/shop/REV-A",
                source_url="https://pay.ldxp.cn/shop/REV-A",
                contact_email="a@example.com",
                status="approved",
                origin="manual",
            ))
            db.add(SourceIntake(
                source_type="ldxp",
                source_key="https://pay.ldxp.cn/shop/REV-B",
                source_url="https://pay.ldxp.cn/shop/REV-B",
                contact_email="b@example.com",
                status="disabled",
                decision_note="手动安全禁用",
                origin="manual",
            ))
            db.commit()
        created = test_client.post(
            "/api/v1/source-policy/requests",
            json={
                "source_url": "https://pay.ldxp.cn/shop/REV-A",
                "request_type": "opt_out",
                "requester_email": "owner@example.com",
                "reason": "opt out",
            },
        ).json()
        applied = test_client.post(
            f"/api/v1/admin/source-policy/requests/{created['id']}/decide",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "verified"},
        )
        assert applied.status_code == 200
        with Session(engine) as db:
            a = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/REV-A"))
            b = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/REV-B"))
            assert a.status == "disabled"
            assert b.status == "disabled"  # manual disabled remains untouched

        reversed_request = test_client.post(
            f"/api/v1/admin/source-policy/requests/{created['id']}/reverse",
            headers={"X-Admin-Key": "admin-policy"},
            json={"decision": "applied", "note": "owner confirmed"},
        )
        assert reversed_request.status_code == 200
        with Session(engine) as db:
            a = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/REV-A"))
            b = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://pay.ldxp.cn/shop/REV-B"))
            assert a.status == "approved"  # restored to previous status
            assert b.status == "disabled"  # manual disabled preserved
