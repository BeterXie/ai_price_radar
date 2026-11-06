from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import SystemSetting
from app.services import bot_ai_settings
from app.services.credential_crypto import decrypt_secret, migrate_bot_credentials
from app.services.snapshot_catalog import SnapshotCatalog
from extensions.bots import price_assistant

HEADERS = {"X-Admin-Key": "ai-settings-test-admin"}
DRAFT = {"enabled": True, "base_url": "https://model.example/v1", "model": "price-model-a", "api_style": "chat_completions", "api_key": "test-private-ai-key"}


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(get_settings(), "admin_api_key", HEADERS["X-Admin-Key"])
    monkeypatch.setattr(bot_ai_settings, "SessionLocal", sessions)
    monkeypatch.setattr(price_assistant, "price_assistant", price_assistant.PriceAssistant())
    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, sessions
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_admin_ai_key_is_encrypted_private_and_can_be_rotated_or_cleared(setup):
    client, sessions = setup
    default = client.get("/api/v1/admin/bot-ai", headers=HEADERS)
    assert default.status_code == 200
    assert default.json() == {"enabled": False, "base_url": "", "model": "", "api_style": "chat_completions", "api_key_configured": False}
    saved = client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=DRAFT)
    assert saved.status_code == 200 and saved.json()["api_key_configured"] is True
    assert saved.headers["cache-control"] == "no-store"
    assert "api_key" not in saved.json() and DRAFT["api_key"] not in saved.text
    with sessions() as db:
        raw = db.get(SystemSetting, bot_ai_settings.SETTING_KEY).value
        encrypted = json.loads(raw)["api_key"]
        assert DRAFT["api_key"] not in raw and encrypted.startswith("enc:v1:")
        assert decrypt_secret(encrypted) == DRAFT["api_key"]
    change = {**DRAFT, "model": "price-model-b", "api_key": ""}
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=change).status_code == 200
    live = bot_ai_settings.load_runtime_config()
    assert live.model == "price-model-b" and live.api_key.get_secret_value() == DRAFT["api_key"]
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json={**change, "api_key": "new-private-key"}).status_code == 200
    assert bot_ai_settings.load_runtime_config().api_key.get_secret_value() == "new-private-key"
    cleared = client.put("/api/v1/admin/bot-ai", headers=HEADERS, json={**change, "enabled": False, "clear_api_key": True})
    assert cleared.status_code == 200 and not cleared.json()["api_key_configured"]
    assert not bot_ai_settings.load_runtime_config().enabled
    assert not bot_ai_settings.load_runtime_config().api_key.get_secret_value()
    public = client.get("/api/v1/meta")
    assert public.status_code == 200
    assert "bot_ai" not in public.text and DRAFT["base_url"] not in public.text and "new-private-key" not in public.text


@pytest.mark.parametrize("path,method", [("/api/v1/admin/bot-ai", "get"), ("/api/v1/admin/bot-ai", "put"), ("/api/v1/admin/bot-ai/test", "post")])
def test_ai_settings_require_admin_authorization(setup, path, method):
    client, _ = setup
    response = client.request(method, path, **({"json": DRAFT} if method != "get" else {}))
    assert response.status_code == 401


def test_failed_updates_leave_saved_config_intact_and_do_not_reuse_key_at_new_host(setup):
    client, _ = setup
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=DRAFT).status_code == 200
    for patch in (
        {"api_key": None, "base_url": "https://other.example/v1"},
        {"api_key": None, "clear_api_key": True},
        {"api_key": "wrong key"},
        {"model": ""},
        {"base_url": "http://external.example/v1"},
        {"base_url": "https://model.example/v1/chat/completions"},
        {"api_key": None, "base_url": "https://model.example/v2"},
    ):
        response = client.put("/api/v1/admin/bot-ai", headers=HEADERS, json={**DRAFT, **patch})
        assert response.status_code in {400, 422}
        assert DRAFT["api_key"] not in response.text
        live = bot_ai_settings.load_runtime_config()
        assert live.base_url == DRAFT["base_url"] and live.model == DRAFT["model"]
        assert live.api_key.get_secret_value() == DRAFT["api_key"]
    switched = {**DRAFT, "base_url": "https://other.example/v1", "api_key": "other-provider-key"}
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=switched).status_code == 200
    assert bot_ai_settings.load_runtime_config().base_url == switched["base_url"]


def test_validation_errors_never_echo_secrets(setup):
    client, _ = setup
    for path in ("/api/v1/admin/bot-ai", "/api/v1/admin/bot-ai/test"):
        response = client.request("PUT" if path.endswith("bot-ai") else "POST", path, headers=HEADERS, json={**DRAFT, "api_key": {"private": DRAFT["api_key"]}})
        assert response.status_code == 422
        assert DRAFT["api_key"] not in response.text and "input" not in response.text


def test_connection_test_uses_draft_without_saving_and_runtime_switches_next_call(setup, monkeypatch):
    client, sessions = setup
    config_session_open = False
    @contextmanager
    def tracked_session():
        nonlocal config_session_open
        with sessions() as db:
            config_session_open = True
            try:
                yield db
            finally:
                config_session_open = False
    monkeypatch.setattr(bot_ai_settings, "SessionLocal", tracked_session)
    catalog = SnapshotCatalog({"search_schema_version": 1, "snapshot_id": "test", "published_at": datetime.now(timezone.utc).isoformat(), "stale_offer_hours": 72, "products": [], "offer_count": 0})
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=DRAFT).status_code == 200
    real_client = httpx.Client
    received = []
    def handle(request):
        assert not config_session_open
        payload = json.loads(request.content)
        received.append((payload["model"], request.headers["authorization"], str(request.url)))
        function = {"name": "plan_price_request", "arguments": json.dumps({"action": "explain", "topics": ["account", "recharge"]})}
        if request.url.path.endswith("/responses"):
            return httpx.Response(200, json={"output": [{"type": "function_call", **function}]})
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"type": "function", "function": function}]}}]})
    monkeypatch.setattr(price_assistant.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    draft = {**DRAFT, "model": "draft-model", "api_key": "draft-key", "api_style": "responses"}
    tested = client.post("/api/v1/admin/bot-ai/test", headers=HEADERS, json=draft)
    assert tested.status_code == 200 and "未保存" in tested.json()["message"]
    assert received[-1] == ("draft-model", "Bearer draft-key", "https://model.example/v1/responses")
    assert bot_ai_settings.load_runtime_config().model == DRAFT["model"]
    assistant = price_assistant.PriceAssistant()
    assert assistant.plan("解释账号代充", catalog, None, ("runtime",)).action == "explain"
    assert received[-1][:2] == (DRAFT["model"], "Bearer " + DRAFT["api_key"])
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=draft).status_code == 200
    assert assistant.plan("再解释一下", catalog, None, ("runtime",)).action == "explain"
    assert received[-1][:2] == ("draft-model", "Bearer draft-key")
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json={**draft, "enabled": False, "api_key": None}).status_code == 200
    count = len(received)
    assert assistant.plan("不用模型", catalog, None, ("runtime",)) is None
    assert len(received) == count


def test_provider_failure_is_sanitized_and_does_not_save_draft(setup, monkeypatch):
    client, _ = setup
    def fail(*args, **kwargs):
        raise price_assistant.AIUnavailable("provider-private-body")
    monkeypatch.setattr(price_assistant.price_assistant, "plan", fail)
    response = client.post("/api/v1/admin/bot-ai/test", headers=HEADERS, json=DRAFT)
    assert response.status_code == 502
    assert "provider-private-body" not in response.text and DRAFT["api_key"] not in response.text
    assert not bot_ai_settings.load_runtime_config().enabled


def test_unavailable_encryption_or_corrupted_credential_fails_closed(setup, monkeypatch):
    client, sessions = setup
    monkeypatch.setattr(get_settings(), "bot_secret_encryption_key", "")
    monkeypatch.setattr(get_settings(), "session_secret_key", "pricememo-auth-secret-key-change-in-production")
    response = client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=DRAFT)
    assert response.status_code == 503
    with sessions() as db:
        assert db.get(SystemSetting, bot_ai_settings.SETTING_KEY) is None
        db.add(SystemSetting(key=bot_ai_settings.SETTING_KEY, value=json.dumps({**DRAFT, "api_key": "unencrypted-private-key"})))
        db.commit()
    with pytest.raises(bot_ai_settings.BotAIConfigurationError):
        bot_ai_settings.load_runtime_config()


def test_ai_key_follows_existing_server_encryption_key_rotation(setup, monkeypatch):
    client, sessions = setup
    assert client.put("/api/v1/admin/bot-ai", headers=HEADERS, json=DRAFT).status_code == 200
    settings = get_settings()
    old_key = settings.bot_secret_encryption_key
    monkeypatch.setattr(settings, "bot_secret_encryption_key", "rotated-ai-encryption-key-at-least-32-bytes")
    monkeypatch.setattr(settings, "bot_secret_encryption_previous_keys", old_key)
    with sessions() as db:
        assert migrate_bot_credentials(db) == 1
    monkeypatch.setattr(settings, "bot_secret_encryption_previous_keys", "")
    assert bot_ai_settings.load_runtime_config().api_key.get_secret_value() == DRAFT["api_key"]
