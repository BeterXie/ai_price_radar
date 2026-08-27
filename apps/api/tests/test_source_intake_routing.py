from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import SourceIntake


@pytest.fixture
def routing_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-test")
    monkeypatch.setattr(settings, "intake_worker_key", "worker-test")

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.clear()


def _add_intake(
    db: Session,
    source_type: str,
    status: str,
    *,
    approved: bool = False,
) -> int:
    source_url = f"https://{source_type.replace('_', '-')}-{status}.example"
    intake = SourceIntake(
        source_type=source_type,
        declared_platform=source_type if source_type != "unknown" else "auto",
        detected_platform=source_type,
        source_key=source_url,
        source_url=source_url,
        shop_name=f"{source_type} shop",
        contact_email="merchant@example.com",
        status=status,
        approved_at=datetime.now(timezone.utc) if approved else None,
    )
    db.add(intake)
    db.flush()
    return intake.id


def test_approval_routes_only_ldxp_to_worker_queue(routing_client):
    client, engine = routing_client
    with Session(engine) as db:
        intake_ids = {
            source_type: _add_intake(db, source_type, "pending_review")
            for source_type in (
                "ldxp", "dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "other", "unknown",
            )
        }
        db.commit()

    expected = {
        "ldxp": (200, "queued"),
        "dujiao_next": (200, "approved"),
        "merchant_json": (200, "approved"),
        "woocommerce": (200, "approved"),
        "16688": (200, "approved"),
        "schema_org": (200, "approved"),
        "other": (409, None),
        "unknown": (409, None),
    }
    for source_type, intake_id in intake_ids.items():
        response = client.post(
            f"/api/v1/admin/source-intakes/{intake_id}/approve",
            headers={"X-Admin-Key": "admin-test"},
        )
        expected_code, expected_status = expected[source_type]
        assert response.status_code == expected_code
        if expected_status is not None:
            assert response.json()["status"] == expected_status

    with Session(engine) as db:
        assert db.get(SourceIntake, intake_ids["other"]).status == "pending_review"
        assert db.get(SourceIntake, intake_ids["unknown"]).status == "pending_review"


def test_retry_preserves_each_source_workflow(routing_client):
    client, engine = routing_client
    with Session(engine) as db:
        intake_ids = {
            "unknown": _add_intake(db, "unknown", "validation_failed"),
            "ldxp": _add_intake(db, "ldxp", "no_products"),
            "dujiao_next": _add_intake(db, "dujiao_next", "validation_failed", approved=True),
            "merchant_json": _add_intake(db, "merchant_json", "validation_failed"),
            "woocommerce": _add_intake(db, "woocommerce", "validation_failed", approved=True),
            "16688": _add_intake(db, "16688", "validation_failed", approved=True),
            "schema_org": _add_intake(db, "schema_org", "validation_failed"),
            "other": _add_intake(db, "other", "validation_failed"),
        }
        db.commit()

    expected = {
        "unknown": (200, "submitted"),
        "ldxp": (200, "queued"),
        "dujiao_next": (200, "approved"),
        "merchant_json": (200, "pending_review"),
        "woocommerce": (200, "approved"),
        "16688": (200, "approved"),
        "schema_org": (200, "pending_review"),
        "other": (409, None),
    }
    for source_type, intake_id in intake_ids.items():
        response = client.post(
            f"/api/v1/admin/source-intakes/{intake_id}/retry",
            headers={"X-Admin-Key": "admin-test"},
        )
        expected_code, expected_status = expected[source_type]
        assert response.status_code == expected_code
        if expected_status is not None:
            assert response.json()["status"] == expected_status

    with Session(engine) as db:
        assert db.get(SourceIntake, intake_ids["other"]).status == "validation_failed"
