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

        def loader(source):
            assert str(source).rstrip("/") == "https://dujiao.example"
            yield {
                "token": "dujiao-example",
                "shop_name": "Dujiao Example",
                "shop_url": "https://dujiao.example",
                "source_platform": "dujiao_next",
                "source_kind": "public_api",
                "product_key": "chatgpt-plus",
                "product_name": "ChatGPT Plus 直充一个月",
                "product_url": "https://dujiao.example/products/chatgpt-plus",
                "listed_price": "88.00",
                "currency": "CNY",
                "stock_count": 1,
                "product_status": "in_stock",
            }

        monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
        pipeline_db = session_for(database_url)
        try:
            sources = approved_intake_sources(pipeline_db)
            assert len(sources) == 1 and sources[0].intake_ids == (intake_id,)
            publish_sources(pipeline_db, sources)
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "published"
            assert intake.product_count == 1
        catalog = client.get("/api/v1/products", params={"source_platform": "dujiao_next"})
        assert catalog.status_code == 200
        assert catalog.json()["offer_count"] == 1
    finally:
        app.dependency_overrides.clear()
