import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import CatalogSnapshot, Product, RelayStation
from app.site_models import SiteArticle

ADMIN = {"X-Admin-Key": "site-test-key"}


@pytest.fixture
def site_db(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", ADMIN["X-Admin-Key"])
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        app.dependency_overrides[get_db] = lambda: db
        yield db, TestClient(app), engine
    app.dependency_overrides.clear()
    engine.dispose()


def article(**changes):
    return {"title": "订阅比较", "slug": "buying-guide", "markdown": "## 看懂报价\n核对库存。", **changes}


def test_articles_are_site_scoped_and_drafts_never_public(site_db):
    db, client, _ = site_db
    prefix = "/api/v1/admin/sites/aiprice/articles"
    assert client.post(prefix, json=article()).status_code == 401
    created = client.post(prefix, headers=ADMIN, json=article())
    assert created.status_code == 201, created.text
    article_id = created.json()["id"]
    assert client.get("/api/v1/sites/aiprice/articles").json()["total"] == 0
    assert client.get("/api/v1/sites/aiprice/articles/buying-guide").status_code == 404
    assert client.get(f"/api/v1/admin/sites/aisi/articles/{article_id}", headers=ADMIN).status_code == 404
    assert client.put(f"/api/v1/admin/sites/aisi/articles/{article_id}", headers=ADMIN, json=article(status="published")).status_code == 404
    assert client.put(f"{prefix}/{article_id}", headers=ADMIN, json=article(status="published")).status_code == 200
    assert client.get("/api/v1/sites/aiprice/articles/buying-guide").json()["markdown"].startswith("##")
    assert client.get("/api/v1/sites/aisi/articles/buying-guide").status_code == 404
    other = client.post("/api/v1/admin/sites/aisi/articles", headers=ADMIN, json=article(title="不同文章", status="published"))
    assert other.status_code == 201
    assert client.post(prefix, headers=ADMIN, json=article()).status_code == 409
    assert client.get("/api/v1/sites/aisi/articles/buying-guide").json()["title"] == "不同文章"
    assert client.put(f"{prefix}/{article_id}", headers=ADMIN, json=article(status="draft")).status_code == 200
    assert client.get("/api/v1/sites/aiprice/articles/buying-guide").status_code == 404
    assert client.get("/api/v1/sites/unknown/articles").status_code == 404
    assert client.get("/api/v1/sites/aiprice/articles?page_size=101").status_code == 422
    assert client.post(prefix, headers=ADMIN, json=article(slug="../secret")).status_code == 422


def test_sites_do_not_share_notices_verification_or_ads(site_db):
    _, client, _ = site_db
    settings = {"notice_title": "A 站公告", "google_verification": "google-a", "baidu_analytics_id": "1" * 32}
    assert client.put("/api/v1/admin/sites/aiprice/settings", headers=ADMIN, json=settings).status_code == 200
    assert client.get("/api/v1/sites/aisi/settings").json()["google_verification"] == ""
    assert client.get("/api/v1/sites/aiprice/settings").json()["notice_title"] == "A 站公告"
    ad = client.post("/api/v1/admin/sites/aiprice/ads", headers=ADMIN, json={"title": "赞助", "link_url": "https://example.com"})
    assert ad.status_code == 201, ad.text
    ad_id = ad.json()["id"]
    assert client.get("/api/v1/sites/aiprice/ads").json()["items"][0]["id"] == ad_id
    assert client.get("/api/v1/sites/aisi/ads").json()["items"] == []
    assert client.post(f"/api/v1/sites/aisi/ads/{ad_id}/click").status_code == 404
    assert client.patch(f"/api/v1/admin/sites/aisi/ads/{ad_id}", headers=ADMIN, json={"title": "changed"}).status_code == 404
    assert client.patch(f"/api/v1/admin/sites/aiprice/ads/{ad_id}", headers=ADMIN, json={"is_enabled": False}).status_code == 200
    assert client.post(f"/api/v1/sites/aiprice/ads/{ad_id}/click").status_code == 404


def test_relays_require_explicit_publication_and_hide_credentials(site_db):
    db, client, _ = site_db
    station = RelayStation(name="Provider", url="https://example.com", base_url="https://example.com/v1", encrypted_api_key="never-public", review_status="approved", is_enabled=True)
    db.add(station)
    db.commit()
    assert client.get("/api/v1/sites/aiprice/relays").json()["items"] == []
    publication = {"tagline": "本站说明", "link_url": "https://example.com/?ref=aiprice", "is_sponsored": True}
    res = client.put(f"/api/v1/admin/sites/aiprice/relays/{station.id}", headers=ADMIN, json=publication)
    assert res.status_code == 200, res.text
    public = client.get("/api/v1/sites/aiprice/relays")
    assert public.json()["items"][0]["tagline"] == "本站说明"
    assert "never-public" not in public.text
    assert client.get("/api/v1/sites/aisi/relays").json()["items"] == []
    assert client.post(f"/api/v1/sites/aisi/relays/{station.id}/click").status_code == 404
    assert client.post(f"/api/v1/sites/aiprice/relays/{station.id}/click").status_code == 200
    db.refresh(station)
    assert station.click_count == 0
    station.review_status = "pending_review"
    db.commit()
    assert client.get("/api/v1/sites/aiprice/relays").json()["items"] == []
    assert client.post(f"/api/v1/sites/aiprice/relays/{station.id}/click").status_code == 404


def test_migration_is_repeatable_and_preserves_shared_catalog(site_db):
    db, _, engine = site_db
    db.add(Product(slug="shared", display_name="Shared", platform="OpenAI"))
    db.commit()
    path = Path(__file__).resolve().parents[3] / "scripts" / "migrate_multi_brand_v26.py"
    spec = importlib.util.spec_from_file_location("multi_brand_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.migrate(engine)
    module.migrate(engine)
    assert db.scalar(select(Product).where(Product.slug == "shared")).display_name == "Shared"
    assert {"site_articles", "site_relays", "site_ads"}.issubset(inspect(engine).get_table_names())
