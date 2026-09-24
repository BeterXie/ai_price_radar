"""Ad slots (广告栏位) and relay stations (中转站) — admin CRUD and public reads."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import AdSlot, RelayStation


ADMIN = {"X-Admin-Key": "admin-promo-test"}


@pytest.fixture
def test_db(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "admin-promo-test")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ad_slot_admin_crud_and_public_visibility(client, test_db):
    # Admin routes are protected.
    assert client.get("/api/v1/admin/ads").status_code == 401

    created = client.post(
        "/api/v1/admin/ads",
        headers=ADMIN,
        json={
            "placement": "catalog_top",
            "title": "  某中转站 · 新用户赠额度 ",
            "description": "按量计费，支持主流模型。",
            "sponsor_name": "示例赞助商",
            "link_url": "https://relay.example.com/?ref=pricememo",
            "image_url": "/brand/logo.svg",
            "sort_order": 10,
        },
    )
    assert created.status_code == 201, created.text
    slot = created.json()
    assert slot["title"] == "某中转站 · 新用户赠额度"
    assert slot["badge"] == "广告"
    assert slot["click_count"] == 0

    # Public read returns the live slot, filtered by placement.
    public = client.get("/api/v1/ads", params={"placement": "catalog_top"}).json()
    assert public["enabled"] is True
    assert [item["id"] for item in public["items"]] == [slot["id"]]
    assert public["items"][0]["link_url"] == "https://relay.example.com/?ref=pricememo"
    assert "click_count" not in public["items"][0]
    assert client.get("/api/v1/ads", params={"placement": "home_hero"}).json()["items"] == []
    assert client.get("/api/v1/ads", params={"placement": "not-a-placement"}).json()["items"] == []

    # Click tracking increments and is visible to admins only.
    clicked = client.post(f"/api/v1/ads/{slot['id']}/click")
    assert clicked.status_code == 200
    assert clicked.json()["click_count"] == 1
    admin_list = client.get("/api/v1/admin/ads", headers=ADMIN).json()
    assert admin_list[0]["click_count"] == 1

    # Disabling hides it from the public list and rejects clicks.
    patched = client.patch(f"/api/v1/admin/ads/{slot['id']}", headers=ADMIN, json={"is_enabled": False})
    assert patched.status_code == 200
    assert patched.json()["is_enabled"] is False
    assert client.get("/api/v1/ads").json()["items"] == []
    assert client.post(f"/api/v1/ads/{slot['id']}/click").status_code == 404

    # Delete.
    assert client.delete(f"/api/v1/admin/ads/{slot['id']}", headers=ADMIN).status_code == 204
    assert client.get("/api/v1/admin/ads", headers=ADMIN).json() == []


def test_ad_slot_rejects_unsafe_links_and_bad_schedule(client):
    for bad_link in ("http://insecure.example.com", "javascript:alert(1)", "https://127.0.0.1/x", "//evil.example.com"):
        response = client.post(
            "/api/v1/admin/ads",
            headers=ADMIN,
            json={"title": "bad", "link_url": bad_link},
        )
        assert response.status_code == 422, bad_link

    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/v1/admin/ads",
        headers=ADMIN,
        json={
            "title": "bad schedule",
            "starts_at": now.isoformat(),
            "ends_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 422


def test_ad_slot_schedule_and_global_toggle(client, test_db):
    now = datetime.now(timezone.utc)
    test_db.add_all([
        AdSlot(placement="home_hero", title="live", sort_order=2),
        AdSlot(placement="home_hero", title="future", starts_at=now + timedelta(days=1), sort_order=1),
        AdSlot(placement="home_hero", title="expired", ends_at=now - timedelta(days=1), sort_order=0),
        AdSlot(placement="home_hero", title="legacy-unsafe-link", link_url="http://plain.example.com", sort_order=3),
    ])
    test_db.commit()

    items = client.get("/api/v1/ads", params={"placement": "home_hero"}).json()["items"]
    assert [item["title"] for item in items] == ["live", "legacy-unsafe-link"]
    # Unsafe legacy links are scrubbed at read time instead of leaking.
    assert items[1]["link_url"] == ""

    meta = client.get("/api/v1/meta").json()
    assert meta["ad_slots_enabled"] is True

    toggled = client.patch("/api/v1/admin/settings", headers=ADMIN, json={"ad_slots_enabled": False})
    assert toggled.status_code == 200
    assert toggled.json()["ad_slots_enabled"] is False
    disabled = client.get("/api/v1/ads", params={"placement": "home_hero"}).json()
    assert disabled == {"items": [], "enabled": False}
    assert client.get("/api/v1/meta").json()["ad_slots_enabled"] is False


def test_relay_station_admin_crud_and_public_list(client, test_db):
    assert client.get("/api/v1/admin/relays").status_code == 401

    created = client.post(
        "/api/v1/admin/relays",
        headers=ADMIN,
        json={
            "name": "  示例中转站 ",
            "url": "https://api.relay-example.com",
            "tagline": "OpenAI / Claude / Gemini 统一接入",
            "supported_models": ["gpt-4.1", "claude-sonnet-4", "gpt-4.1", " "],
            "price_note": "官方价 0.7 折起",
            "billing_note": "按量计费 · 支持支付宝",
            "tags": ["支持 Claude", "余额永久有效"],
            "sort_order": 5,
        },
    )
    assert created.status_code == 201, created.text
    station = created.json()
    assert station["name"] == "示例中转站"
    assert station["supported_models"] == ["gpt-4.1", "claude-sonnet-4"]
    assert station["url"] == "https://api.relay-example.com/"

    second = client.post(
        "/api/v1/admin/relays",
        headers=ADMIN,
        json={"name": "赞助中转站", "url": "https://sponsor.example.com", "is_sponsored": True, "sort_order": 99},
    )
    assert second.status_code == 201
    hidden = client.post(
        "/api/v1/admin/relays",
        headers=ADMIN,
        json={"name": "下线中转站", "url": "https://offline.example.com", "is_enabled": False},
    )
    assert hidden.status_code == 201

    public = client.get("/api/v1/relays").json()
    assert public["enabled"] is True
    assert public["total"] == 2
    # Sponsored entries lead, then sort_order.
    assert [item["name"] for item in public["items"]] == ["赞助中转站", "示例中转站"]
    assert public["items"][0]["is_sponsored"] is True

    meta = client.get("/api/v1/meta").json()
    assert meta["relay_hub_enabled"] is True
    assert meta["relay_station_count"] == 2

    clicked = client.post(f"/api/v1/relays/{station['id']}/click")
    assert clicked.status_code == 200 and clicked.json()["click_count"] == 1
    assert client.post(f"/api/v1/relays/{hidden.json()['id']}/click").status_code == 404

    patched = client.patch(
        f"/api/v1/admin/relays/{station['id']}",
        headers=ADMIN,
        json={"tags": ["新标签"], "price_note": "限时 5 折"},
    )
    assert patched.status_code == 200
    assert patched.json()["tags"] == ["新标签"]
    assert patched.json()["price_note"] == "限时 5 折"
    assert patched.json()["supported_models"] == ["gpt-4.1", "claude-sonnet-4"]

    assert client.delete(f"/api/v1/admin/relays/{station['id']}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/v1/admin/relays/{station['id']}", headers=ADMIN).status_code == 404


def test_relay_station_rejects_unsafe_urls_and_respects_toggle(client, test_db):
    for bad in ("http://relay.example.com", "https://localhost:8080", "https://10.0.0.8/api", "ftp://relay.example.com"):
        response = client.post("/api/v1/admin/relays", headers=ADMIN, json={"name": "bad", "url": bad})
        assert response.status_code == 422, bad

    test_db.add(RelayStation(name="legacy", url="http://legacy.example.com"))
    test_db.commit()
    items = client.get("/api/v1/relays").json()["items"]
    assert items[0]["url"] == ""

    toggled = client.patch("/api/v1/admin/settings", headers=ADMIN, json={"relay_hub_enabled": False})
    assert toggled.json()["relay_hub_enabled"] is False
    assert client.get("/api/v1/relays").json() == {"items": [], "total": 0, "enabled": False}
    meta = client.get("/api/v1/meta").json()
    assert meta["relay_hub_enabled"] is False
    assert meta["relay_station_count"] == 0
