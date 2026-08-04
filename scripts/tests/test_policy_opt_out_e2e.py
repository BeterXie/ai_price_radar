from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "pipeline"))

from app.core.config import get_settings
from app.database import Base as ApiBase, get_db
from app.main import app
from app.models import SourceIntake
from connectors import CONNECTORS
from publish_catalog import approved_intake_sources, publish_sources
from common import session_for


def test_opt_out_disables_intake_and_removes_from_next_publish(tmp_path, monkeypatch):
    database_path = tmp_path / "policy-e2e.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-e2e")
    monkeypatch.setattr(settings, "discovery_worker_key", "discovery-e2e")

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as db:
            db.add(SourceIntake(
                source_type="dujiao_next",
                declared_platform="auto",
                detected_platform="dujiao_next",
                source_key="https://shop.example.com",
                source_url="https://shop.example.com",
                contact_email="owner@example.com",
                status="approved",
                approved_at=__import__("app.services.source_intake", fromlist=["utcnow"]).utcnow(),
                origin="manual",
            ))
            db.commit()

        calls = []

        def loader(source):
            calls.append(str(source))
            yield {
                "token": "dujiao-e2e",
                "shop_name": "Test Shop",
                "shop_url": "https://shop.example.com",
                "source_platform": "dujiao_next",
                "source_kind": "public_api",
                "product_key": "P1",
                "product_name": "ChatGPT Plus 直充",
                "product_url": "https://shop.example.com/products/chatgpt",
                "listed_price": "88.00",
                "currency": "CNY",
                "stock_count": 1,
                "product_status": "in_stock",
            }

        monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
        pipeline_db = session_for(database_url)
        try:
            sources = approved_intake_sources(pipeline_db)
            assert len(sources) == 1
            publish_sources(pipeline_db, sources)
        finally:
            pipeline_db.close()
        assert len(calls) == 1

        client = TestClient(app)
        created = client.post("/api/v1/source-policy/requests", json={
            "source_url": "https://shop.example.com",
            "request_type": "opt_out",
            "requester_email": "owner@example.com",
            "reason": "please remove",
        })
        assert created.status_code == 201
        check = client.get(
            "/api/v1/internal/source-policy/check",
            params={"source_url": "https://shop.example.com"},
            headers={"X-Discovery-Worker-Key": "discovery-e2e"},
        ).json()
        assert check["source_status"] == "legal_hold"

        decided = client.post(
            f"/api/v1/admin/source-policy/requests/{created.json()['id']}/decide",
            headers={"X-Admin-Key": "admin-e2e"},
            json={"decision": "applied", "note": "verified owner"},
        )
        assert decided.status_code == 200

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.source_key == "https://shop.example.com"))
            assert intake.status == "disabled"

        pipeline_db = session_for(database_url)
        try:
            assert approved_intake_sources(pipeline_db) == []
        finally:
            pipeline_db.close()
        assert len(calls) == 1
    finally:
        app.dependency_overrides.clear()
