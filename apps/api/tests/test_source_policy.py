from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import Base as ApiBase, get_db
from app.main import app
from app.models import SourceIntake, SourcePolicyRequest


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
        assert body["status"] == "pending"
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
