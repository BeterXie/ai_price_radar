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
from app.models import SourceCandidate, SourceIntake  # noqa: E402
from connectors import CONNECTORS  # noqa: E402
from publish_catalog import approved_intake_sources, publish_sources  # noqa: E402
from common import session_for  # noqa: E402


DISCOVERY_HEADERS = {"X-Discovery-Worker-Key": "discovery-e2e"}
ADMIN_HEADERS = {"X-Admin-Key": "admin-e2e"}


def _setup(tmp_path, monkeypatch):
    database_path = tmp_path / "discovery-e2e.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-e2e")
    monkeypatch.setattr(settings, "discovery_worker_key", "discovery-e2e")
    monkeypatch.setattr(settings, "discovery_dujiao_auto_approve", True)
    monkeypatch.setattr(settings, "discovery_woocommerce_auto_approve", True)
    monkeypatch.setattr(settings, "discovery_schema_auto_approve", False)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return engine, database_url, TestClient(app)


def _cleanup():
    app.dependency_overrides.clear()


def _upsert_claim_report(
    client,
    *,
    url: str,
    hint: str,
    platform: str,
    source_key: str,
    source_url: str,
    ai_product_count: int = 1,
    total_product_count: int = 2,
    confidence: int = 90,
):
    response = client.post(
        "/api/v1/internal/source-candidates/upsert",
        headers=DISCOVERY_HEADERS,
        json={
            "discovered_url": url,
            "platform_hint": hint,
            "discovered_by": "bing",
            "matched_query": '"ChatGPT Plus" "add to cart"',
        },
    )
    assert response.status_code == 200
    candidate_id = response.json()["candidate_id"]
    claimed = client.post(
        "/api/v1/internal/source-candidates/claim",
        headers=DISCOVERY_HEADERS,
        json={"limit": 1, "lease_seconds": 300},
    ).json()
    assert claimed and claimed[0]["candidate_id"] == candidate_id
    reported = client.post(
        f"/api/v1/internal/source-candidates/{candidate_id}/result",
        headers=DISCOVERY_HEADERS,
        json={
            "status": "detected",
            "attempt_count": claimed[0]["attempt_count"],
            "detected_platform": platform,
            "detected_source_key": source_key,
            "detected_source_url": source_url,
            "total_product_count": total_product_count,
            "ai_product_count": ai_product_count,
            "sample_products": [{
                "name": "ChatGPT Plus 月卡",
                "url": f"{source_url.rstrip('/')}/products/chatgpt-plus",
                "product_slug": "chatgpt-plus",
            }],
            "fingerprints": ["e2e-fingerprint"],
            "confidence_score": confidence,
            "failure_reason": "",
        },
    )
    assert reported.status_code == 200
    return candidate_id, reported.json()


def test_dujiao_candidate_auto_approves_and_publishes_atomically(tmp_path, monkeypatch):
    engine, database_url, client = _setup(tmp_path, monkeypatch)
    try:
        candidate_id, reported = _upsert_claim_report(
            client,
            url="https://dujiao-e2e.example.com",
            hint="dujiao_next",
            platform="dujiao_next",
            source_key="https://dujiao-e2e.example.com",
            source_url="https://dujiao-e2e.example.com",
        )
        assert reported["status"] == "promoted"
        assert reported["detected_platform"] == "dujiao_next"

        def loader(source):
            assert str(source).rstrip("/") == "https://dujiao-e2e.example.com"
            yield {
                "token": "dujiao-e2e",
                "shop_name": "Dujiao E2E",
                "shop_url": "https://dujiao-e2e.example.com",
                "source_platform": "dujiao_next",
                "source_kind": "public_api",
                "product_key": "chatgpt-plus",
                "product_name": "ChatGPT Plus 直充一个月",
                "product_url": "https://dujiao-e2e.example.com/products/chatgpt-plus",
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

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == reported["promoted_intake_id"]))
            assert intake.status == "published"
            assert intake.product_count == 1
            assert intake.origin == "discovery"
            candidate = db.scalar(select(SourceCandidate).where(SourceCandidate.id == candidate_id))
            assert candidate.status == "promoted"
        catalog = client.get("/api/v1/products", params={"source_platform": "dujiao_next"})
        assert catalog.status_code == 200
        assert catalog.json()["offer_count"] == 1
    finally:
        _cleanup()


def test_woocommerce_candidate_publishes_with_shop_platform(tmp_path, monkeypatch):
    engine, database_url, client = _setup(tmp_path, monkeypatch)
    try:
        _candidate_id, reported = _upsert_claim_report(
            client,
            url="https://woo-e2e.example.com/products/chatgpt",
            hint="unknown",
            platform="woocommerce",
            source_key="https://woo-e2e.example.com",
            source_url="https://woo-e2e.example.com",
        )
        assert reported["status"] == "promoted"
        assert reported["promoted_intake_id"] is not None

        def loader(source):
            assert str(source).rstrip("/") == "https://woo-e2e.example.com"
            yield {
                "token": "woocommerce-store-e2e",
                "shop_name": "Woo E2E",
                "shop_url": "https://woo-e2e.example.com",
                "source_platform": "woocommerce",
                "source_kind": "public_api",
                "product_key": "woocommerce:1",
                "product_name": "ChatGPT Plus 1 month",
                "product_url": "https://woo-e2e.example.com/product/chatgpt-plus",
                "listed_price": "88.00",
                "currency": "CNY",
                "stock_count": 1,
                "product_status": "in_stock",
                "is_purchasable": True,
            }

        monkeypatch.setitem(CONNECTORS, "woocommerce-store", loader)
        pipeline_db = session_for(database_url)
        try:
            sources = approved_intake_sources(pipeline_db)
            assert len(sources) == 1
            publish_sources(pipeline_db, sources)
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == reported["promoted_intake_id"]))
            assert intake.status == "published"
        catalog = client.get("/api/v1/products", params={"source_platform": "woocommerce"})
        assert catalog.status_code == 200
        assert catalog.json()["offer_count"] == 1
        meta = client.get("/api/v1/meta").json()
        assert any(item["id"] == "woocommerce" for item in meta["source_platforms"])
    finally:
        _cleanup()


def test_schema_org_sitemap_stays_exact_and_publishes_after_admin_approval(tmp_path, monkeypatch):
    engine, database_url, client = _setup(tmp_path, monkeypatch)
    try:
        sitemap_url = "https://schema-e2e.example.com/product-sitemap.xml"
        _candidate_id, reported = _upsert_claim_report(
            client,
            url=sitemap_url,
            hint="schema_org",
            platform="schema_org",
            source_key=sitemap_url,
            source_url=sitemap_url,
            total_product_count=3,
            confidence=80,
        )
        assert reported["status"] == "promoted"
        intake_id = reported["promoted_intake_id"]
        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "pending_review"
            assert intake.source_url == sitemap_url
            assert intake.source_key == sitemap_url

        approved = client.post(
            f"/api/v1/admin/source-intakes/{intake_id}/approve",
            headers=ADMIN_HEADERS,
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        def loader(source):
            assert str(source) == sitemap_url
            yield {
                "token": "schema-org-e2e",
                "shop_name": "Schema E2E",
                "shop_url": "https://schema-e2e.example.com",
                "source_platform": "schema_org",
                "source_kind": "sitemap_jsonld",
                "product_key": "url:https://schema-e2e.example.com/products/chatgpt",
                "product_name": "ChatGPT Plus 订阅",
                "product_url": "https://schema-e2e.example.com/products/chatgpt",
                "listed_price": "99.00",
                "currency": "CNY",
                "stock_count": 1,
                "product_status": "in_stock",
            }

        monkeypatch.setitem(CONNECTORS, "schema-org", loader)
        pipeline_db = session_for(database_url)
        try:
            sources = approved_intake_sources(pipeline_db)
            assert len(sources) == 1
            publish_sources(pipeline_db, sources)
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "published"
        catalog = client.get("/api/v1/products", params={"source_platform": "schema_org"})
        assert catalog.status_code == 200
        assert catalog.json()["offer_count"] == 1
    finally:
        _cleanup()


def test_woocommerce_no_public_offers_stays_no_products_and_meta_unchanged(tmp_path, monkeypatch):
    engine, database_url, client = _setup(tmp_path, monkeypatch)
    try:
        _candidate_id, reported = _upsert_claim_report(
            client,
            url="https://woo-empty.example.com/products/chatgpt",
            hint="unknown",
            platform="woocommerce",
            source_key="https://woo-empty.example.com",
            source_url="https://woo-empty.example.com",
        )
        intake_id = reported["promoted_intake_id"]

        def empty_loader(_source):
            return iter(())

        monkeypatch.setitem(CONNECTORS, "woocommerce-store", empty_loader)
        pipeline_db = session_for(database_url)
        try:
            sources = approved_intake_sources(pipeline_db)
            assert len(sources) == 1
            publish_sources(pipeline_db, sources)
        finally:
            pipeline_db.close()

        with Session(engine) as db:
            intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id))
            assert intake.status == "no_products"
            assert intake.product_count == 0
        meta = client.get("/api/v1/meta").json()
        assert all(item["id"] != "woocommerce" for item in meta["source_platforms"])
    finally:
        _cleanup()
