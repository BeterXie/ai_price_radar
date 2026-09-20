from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "pipeline"))

from app.core.config import get_settings  # noqa: E402
from app.database import Base as ApiBase, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import SourceIntake  # noqa: E402
from publish_catalog import approved_intake_sources  # noqa: E402
from common import session_for  # noqa: E402


def test_dujiao_submission_detection_approval_and_atomic_publication(tmp_path, monkeypatch):
    database_path = tmp_path / "intake-e2e.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")
    monkeypatch.setattr(settings, "detector_worker_key", "detector-test")
    monkeypatch.setattr(settings, "report_rate_limit_count", 100)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        submitted = client.post("/api/v1/shop-requests", json={
            "source_type": "dujiao_next",
            "shop_url": "https://dujiao.example",
            "shop_name": "Dujiao Example",
            "contact": "owner@example.com",
        })
        assert submitted.status_code == 201
        intake_id = submitted.json()["request_id"]
        assert submitted.json()["workflow_status"] == "submitted"

        detector_headers = {"X-Detector-Worker-Key": "detector-test"}
        task = client.post(
            "/api/v1/internal/source-detections/claim",
            headers=detector_headers,
            json={"limit": 1, "lease_seconds": 300},
        ).json()[0]
        detected = client.post(
            f"/api/v1/internal/source-detections/{intake_id}/result",
            headers=detector_headers,
            json={
                "status": "pending_review",
                "attempt_count": task["attempt_count"],
                "detected_platform": "dujiao_next",
                "source_url": "https://dujiao.example",
                "source_key": "https://dujiao.example",
                "shop_name": "Dujiao Example",
                "product_count": 1,
            },
        )
        assert detected.status_code == 200
        approved = client.post(
            f"/api/v1/admin/source-intakes/{intake_id}/approve",
            headers={"X-Admin-Key": "admin-test"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        # v3.7.42 (c70e22d) 起发布器完全排除 dujiao_next：收录工作流可以走到
        # approved，但发布门禁不会为它生成发布任务，也不会产生公开 offer。
        pipeline_db = session_for(database_url)
        try:
            assert approved_intake_sources(pipeline_db) == []
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "approved"
            assert intake.product_count == 1
    finally:
        app.dependency_overrides.clear()
