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
from app.models import SourceIntake, User  # noqa: E402
from app.security import require_current_user  # noqa: E402
from connectors import CONNECTORS  # noqa: E402
from publish_catalog import approved_intake_sources, publish_sources  # noqa: E402
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
    monkeypatch.setattr(settings, "shop_intake_auto_approve", False)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_current_user] = lambda: User(id=1, email="owner@example.com")
    try:
        client = TestClient(app)
        submitted = client.post("/api/v1/shop-requests", json={
            "source_type": "independent",
            "shop_url": "https://dujiao.example",
            "shop_name": "Dujiao Example",
            "contact": "owner@example.com",
            "authorization_confirmed": True,
            "consent_version": "shop-source-submission-v1",
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
        with Session(engine) as db:
            intake = db.get(SourceIntake, intake_id)
            assert intake.status == "pending_review"
            assert intake.source_type == "dujiao_next"
            assert intake.declared_platform == "independent"
        approved = client.post(
            f"/api/v1/admin/source-intakes/{intake_id}/approve",
            headers={"X-Admin-Key": "admin-test"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        def loader(source):
            assert str(source).rstrip("/") == "https://dujiao.example"
            yield {
                "token": "dujiao-e2e", "shop_name": "Dujiao Example",
                "shop_url": "https://dujiao.example", "source_platform": "dujiao_next",
                "product_key": "dujiao:1", "product_name": "ChatGPT Plus 独享成品号 一个月",
                "product_url": "https://dujiao.example/product/1", "listed_price": "88.00",
                "currency": "CNY", "stock_count": 1, "product_status": "in_stock",
            }

        monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
        pipeline_db = session_for(database_url)
        try:
            for _ in range(2):
                sources = approved_intake_sources(pipeline_db)
                assert len(sources) == 1 and sources[0].connector == "dujiao-next"
                assert publish_sources(pipeline_db, sources).offer_count == 1
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "published"
            assert intake.product_count == 1
        catalog = client.get("/api/v1/products", params={"source_platform": "independent"}).json()
        assert catalog["offer_count"] == 1
        offers = client.get("/api/v1/products/chatgpt-plus/offers", params={"source_platform": "independent"}).json()
        assert len(offers["items"]) == 1 and offers["items"][0]["source_platform"] == "dujiao_next"
        assert [item["id"] for item in client.get("/api/v1/meta").json()["source_platforms"]] == ["independent"]
    finally:
        app.dependency_overrides.clear()
