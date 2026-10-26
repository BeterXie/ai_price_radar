import io
import json
import socket
from datetime import datetime, timedelta, timezone
from http.client import BadStatusLine

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import RelayProbeResult, RelayStation, SystemSetting, User
from app.security import require_current_user
from app.services.credential_crypto import decrypt_secret, encrypt_secret
from app.services.relay_monitor import claim_probe, configure_relay, probe_relay, relay_health, run_due_probes

ADMIN = {"X-Admin-Key": "relay-admin-test"}
KEY = "sk-relay-test-only"


@pytest.fixture
def relay_api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(email="owner@example.com")
        db.add(user)
        db.commit()
        user_id = user.id
    monkeypatch.setattr(get_settings(), "admin_api_key", "relay-admin-test")

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_current_user] = lambda: User(id=user_id, email="owner@example.com")
    try:
        yield TestClient(app), factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def payload(**values):
    return {
        "name": "测试中转站", "url": "https://relay.example.com",
        "base_url": "https://api.example.com/proxy/v1/", "api_key": KEY,
        "probe_model": "test-model", "probe_protocol": "openai",
        "tagline": "多模型统一接入", "description": "提供公开 API 接入，余额长期有效。",
        "price_note": "按官网公示模型价格计费", "billing_note": "预付费，按量计费",
        "contact": "owner@example.com", "authorization_confirmed": True,
        **values,
    }


def test_public_icon_only_fetches_enabled_approved_sites_without_probe_secrets(relay_api, monkeypatch):
    from app.routers import public
    from app.services.relay_icons import RelayIcon

    client, factory = relay_api
    calls = []
    monkeypatch.setattr(public, "get_relay_icon", lambda url: calls.append(url) or RelayIcon(b"test-image", "image/png"))
    with factory() as db:
        station = RelayStation(name="Icon", url="https://relay.example.com", base_url="https://private-probe.example.com/v1", encrypted_api_key="private", is_enabled=True, review_status="pending")
        db.add(station)
        db.commit()
        station_id = station.id
    path = f"/api/v1/relays/{station_id}/icon"
    assert client.get(path).status_code == 404
    assert calls == []
    with factory() as db:
        db.get(RelayStation, station_id).review_status = "approved"
        db.commit()
    response = client.get(path)
    assert response.status_code == 200 and response.content == b"test-image"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]
    assert calls == ["https://relay.example.com"]
    with factory() as db:
        db.get(RelayStation, station_id).is_enabled = False
        db.commit()
    assert client.get(path).status_code == 404
    with factory() as db:
        db.get(RelayStation, station_id).is_enabled = True
        db.add(SystemSetting(key="relay_hub_enabled", value="false"))
        db.commit()
    assert client.get(path).status_code == 404
    assert calls == ["https://relay.example.com"]


def test_missing_public_icon_is_a_non_cached_404(relay_api, monkeypatch):
    from app.routers import public

    client, factory = relay_api
    monkeypatch.setattr(public, "get_relay_icon", lambda url: None)
    with factory() as db:
        station = RelayStation(name="No icon", url="https://relay.example.com", review_status="approved", is_enabled=True)
        db.add(station)
        db.commit()
        station_id = station.id
    response = client.get(f"/api/v1/relays/{station_id}/icon")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_busy_public_icon_can_be_retried_instead_of_negative_cached(relay_api, monkeypatch):
    from app.routers import public

    client, factory = relay_api

    def busy(_url):
        raise public.RelayIconBusy()

    monkeypatch.setattr(public, "get_relay_icon", busy)
    with factory() as db:
        station = RelayStation(name="Busy", url="https://relay.example.com", review_status="approved", is_enabled=True)
        db.add(station)
        db.commit()
        station_id = station.id
    response = client.get(f"/api/v1/relays/{station_id}/icon")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert response.headers["cache-control"] == "no-store"


class FakeClient:
    def __init__(self, status=200, body=None, error=None):
        self.status = status
        self.body = {"choices": [{"message": {"content": "OK"}}]} if body is None else body
        self.error = error
        self.calls = []
        self.model_calls = []
        self.usage_calls = []

    def get(self, url, *, headers, accept):
        from price_radar_http import PinnedResponse
        if url.endswith("/usage"):
            self.usage_calls.append(url)
            return PinnedResponse(404, {}, b"{}")
        self.model_calls.append(url)
        return PinnedResponse(200, {}, b'{"data":[{"id":"test-model"}]}')

    def post_json(self, url, body, *, headers, accept="application/json", on_chunk=None):
        self.calls.append((url, body, headers))
        if self.error:
            raise self.error
        from price_radar_http import PinnedResponse
        return PinnedResponse(self.status, {}, json.dumps(self.body).encode())


def test_submission_is_private_until_approved_and_duplicates_cannot_replace_key(relay_api):
    client, factory = relay_api
    private_note = "仅管理员可见的申请说明"
    profile = {
        "tagline": " 多模型统一接入 ", "description": " 接入 OpenAI 与 Claude\n余额长期有效，退款规则见官网。 ",
        "supported_models": [" model-a ", "model-b", "model-a"],
        "tags": [" 支持支付宝 ", "余额不过期", "支持支付宝"],
        "price_note": " 官方价 0.7 折起 ", "billing_note": " 按量计费 / 包月套餐 ",
    }
    expected_profile = {**{key: value.strip() for key, value in profile.items() if isinstance(value, str)}, "supported_models": ["model-a", "model-b"], "tags": ["支持支付宝", "余额不过期"]}
    response = client.post("/api/v1/relay-requests", json=payload(**profile, is_enabled=True, is_sponsored=True, note=private_note))
    assert response.status_code == 201, response.text
    station_id = response.json()["request_id"]
    assert client.get("/api/v1/relays").json()["items"] == []
    with factory() as db:
        station = db.get(RelayStation, station_id)
        assert station.review_status == "pending"
        assert not station.is_enabled and not station.is_sponsored
        assert station.base_url == "https://api.example.com/proxy/v1"
        assert station.submission_note == private_note
        assert {key: getattr(station, key) for key in expected_profile} == expected_profile
        assert station.encrypted_api_key.startswith("enc:v1:")
        assert decrypt_secret(station.encrypted_api_key) == KEY
    duplicate = client.post("/api/v1/relay-requests", json=payload(api_key="another-key"))
    assert duplicate.json()["status"] == "already_pending"
    assert KEY not in duplicate.text and "another-key" not in duplicate.text
    admin = client.get("/api/v1/admin/relays", headers=ADMIN)
    assert admin.status_code == 200
    assert admin.json()[0]["has_api_key"] is True
    assert admin.json()[0]["submission_note"] == private_note
    assert {key: admin.json()[0][key] for key in expected_profile} == expected_profile
    assert KEY not in admin.text and "encrypted_api_key" not in admin.text
    approved = client.patch(f"/api/v1/admin/relays/{station_id}", headers=ADMIN, json={"review_status": "approved", "is_enabled": True})
    assert approved.status_code == 200, approved.text
    public_response = client.get("/api/v1/relays")
    public = public_response.json()["items"][0]
    assert public["health"]["status"] == "not_checked"
    assert {key: public[key] for key in expected_profile} == expected_profile
    assert not {"base_url", "api_key", "contact_email", "submitted_by", "submission_note"}.intersection(public)
    assert private_note not in public_response.text
    with factory() as db:
        assert decrypt_secret(db.get(RelayStation, station_id).encrypted_api_key) == KEY


@pytest.mark.parametrize("base_url", ["https://127.0.0.1/v1", "http://api.example.com", "https://api.example.com:8443/v1", "https://api.example.com/v1?key=secret", "https://user:pass@api.example.com/v1"])
def test_submission_rejects_unsafe_endpoints(relay_api, base_url):
    client, _ = relay_api
    assert client.post("/api/v1/relay-requests", json=payload(base_url=base_url)).status_code == 422


def test_submission_requires_owner_email_and_credentials(relay_api):
    client, _ = relay_api
    assert client.post("/api/v1/relay-requests", json=payload(contact="someone@example.com")).status_code == 403
    assert client.post("/api/v1/relay-requests", json=payload(api_key="")).status_code == 422
    assert client.post("/api/v1/relay-requests", json=payload(authorization_confirmed=False)).status_code == 422


@pytest.mark.parametrize("field", ["tagline", "description", "price_note", "billing_note"])
@pytest.mark.parametrize("value", [None, "", " \n "])
def test_submission_requires_complete_public_profile(relay_api, field, value):
    client, factory = relay_api
    request = payload()
    if value is None:
        request.pop(field)
    else:
        request[field] = value
    response = client.post("/api/v1/relay-requests", json=request)
    assert response.status_code == 422
    assert any(field in error["loc"] for error in response.json()["detail"])
    with factory() as db:
        assert db.scalar(select(RelayStation)) is None


@pytest.mark.parametrize("values", [
    {"tagline": "a" * 161}, {"description": "a" * 2001},
    {"price_note": "a" * 201}, {"billing_note": "a" * 121},
    {"supported_models": [f"model-{n}" for n in range(41)]}, {"supported_models": ["m" * 61]},
    {"tags": [f"tag-{n}" for n in range(13)]}, {"tags": ["t" * 31]},
])
def test_submission_rejects_profile_over_limits_without_exposing_key(relay_api, values):
    client, _ = relay_api
    response = client.post("/api/v1/relay-requests", json=payload(**values))
    assert response.status_code == 422
    assert KEY not in response.text


def test_invalid_submission_never_echoes_key_in_validation_errors(relay_api):
    client, _ = relay_api
    for values in ({"probe_model": ""}, {"api_key": KEY + "\r\nInjected: value"}):
        response = client.post("/api/v1/relay-requests", json=payload(**values))
        assert response.status_code == 422
        assert KEY not in response.text
        assert all("input" not in error for error in response.json()["detail"])


def test_rejection_stops_monitoring_and_approval_is_explicit(relay_api):
    client, _ = relay_api
    station_id = client.post("/api/v1/relay-requests", json=payload()).json()["request_id"]
    path = f"/api/v1/admin/relays/{station_id}"
    pending = client.patch(path, headers=ADMIN, json={"is_enabled": True}).json()
    assert pending["review_status"] == "pending" and not pending["is_enabled"]
    assert client.post(path + "/probe", headers=ADMIN).status_code == 409
    rejected = client.patch(path, headers=ADMIN, json={"review_status": "rejected"}).json()
    assert not rejected["monitor_enabled"] and not rejected["is_enabled"]
    assert client.get("/api/v1/relays").json()["items"] == []
    approved = client.patch(path, headers=ADMIN, json={"review_status": "approved", "is_enabled": True, "monitor_enabled": True})
    assert approved.status_code == 200 and approved.json()["is_enabled"]
    assert len(client.get("/api/v1/relays").json()["items"]) == 1


@pytest.mark.parametrize(("protocol", "base", "suffix", "header", "response"), [
    ("openai", "https://api.example.com/proxy/v1", "/proxy/v1/chat/completions", "Authorization", {"choices": [{"message": {"content": "OK"}}]}),
    ("anthropic", "https://api.example.com/prefix", "/prefix/v1/messages", "x-api-key", {"content": [{"type": "text", "text": "OK"}]}),
    ("gemini", "https://api.example.com/v1beta", "/v1beta/models/test-model:streamGenerateContent?alt=sse", "x-goog-api-key", {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}),
])
def test_probe_sends_real_completion_to_configured_prefix(relay_api, protocol, base, suffix, header, response):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", monitor_revision=1)
        configure_relay(db, station, {"base_url": base, "probe_protocol": protocol, "probe_model": "test-model", "monitor_enabled": True}, SecretStr(KEY))
        db.add(station)
        db.commit()
        fake = FakeClient(body=response)
        result = probe_relay(db, station, client=fake)
        assert result.status == "healthy"
        url, request, headers = fake.calls[0]
        assert url.endswith(suffix)
        assert KEY in headers[header]
        assert KEY not in url and KEY not in json.dumps(request)
        assert result.first_token_ms is None  # A JSON fallback is not streaming TTFT.
        health = relay_health(db, station)
        assert health.success_rate_24h == 100 and health.sample_count_24h == 1


@pytest.mark.parametrize(("status", "body", "expected"), [
    (401, {}, "credential_error"), (403, {}, "credential_error"),
    (404, {}, "config_error"), (429, {}, "rate_limited"),
    (503, {}, "unhealthy"), (200, {"data": [{"id": "model"}]}, "invalid_response"),
    (200, {"choices": [{"message": {"content": ""}}]}, "invalid_response"),
])
def test_probe_does_not_mistake_model_listing_or_error_for_health(relay_api, status, body, expected):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", base_url="https://api.example.com/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        result = probe_relay(db, station, client=FakeClient(status, body))
        assert result.status == expected
        health = relay_health(db, station)
        if expected in ("credential_error", "config_error"):
            assert health.success_rate_24h is None and health.sample_count_24h == 0
        else:
            assert health.success_rate_24h == 0


@pytest.mark.parametrize(("protocol", "body"), [
    ("openai", {"choices": [{"message": {"content": [{"type": "image_url", "image_url": "x"}]}}]}),
    ("openai", {"choices": [{"message": {"content": {"text": "OK"}}}]}),
    ("openai", {"choices": [{"message": {"content": "  "}}]}),
    ("anthropic", {"content": "OK"}),
    ("gemini", {"candidates": [{"content": {"parts": None}}]}),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": 42}]}}]}),
])
def test_malformed_completion_is_not_healthy_and_does_not_crash(relay_api, protocol, body):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", base_url="https://api.example.com/v1", probe_model="test-model", probe_protocol=protocol, monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        assert probe_relay(db, station, client=FakeClient(body=body)).status == "invalid_response"


@pytest.mark.parametrize(("error", "expected"), [
    (TimeoutError("upstream timeout"), "timeout"),
    (OSError("connection closed"), "connection_error"),
    (BadStatusLine("bad upstream " + KEY), "connection_error"),
])
def test_transport_failure_is_recorded_without_sensitive_error_text(relay_api, error, expected):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", base_url="https://api.example.com/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        result = probe_relay(db, station, client=FakeClient(error=error))
        assert result.status == expected
        assert KEY not in relay_health(db, station).model_dump_json()


@pytest.mark.parametrize(("header_delay", "body_delays", "expected", "elapsed_ms"), [
    (16, (0, 0), "healthy", 16000),
    (31, (0, 0), "timeout", 30000),
    (20, (20, 6), "timeout", 45000),
])
def test_probe_allows_slow_model_headers_but_bounds_idle_and_total_time(
    relay_api, monkeypatch, header_delay, body_delays, expected, elapsed_ms,
):
    from price_radar_http import PinnedHTTPSClient

    _, factory = relay_api
    clock = [100.0]
    monkeypatch.setattr("app.services.relay_monitor.time.monotonic", lambda: clock[0])
    parts = [b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n', b'data: [DONE]\n\n']
    body = b"".join(parts)
    wire = (f"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            f"Content-Length: {len(body)}\r\n\r\n").encode() + body

    class ResponseBody(io.BytesIO):
        part_index = 0

        def readline(self, *args):
            if self.tell() == 0:
                transport.wait(header_delay)
            return super().readline(*args)

        def read1(self, size):
            if self.part_index < len(parts):
                transport.wait(body_delays[self.part_index])
                size = min(size, len(parts[self.part_index]))
                self.part_index += 1
            return super().read1(size)

    class Transport:
        closed = False

        def settimeout(self, seconds):
            self.timeout = seconds

        def wait(self, seconds):
            clock[0] += min(seconds, self.timeout)
            if seconds > self.timeout:
                raise TimeoutError("simulated upstream wait")

        def sendall(self, _request):
            pass

        def makefile(self, *_args):
            return ResponseBody(wire)

        def wrap_socket(self, raw, **_kwargs):
            return raw

        def close(self):
            self.closed = True

    transport = Transport()
    monkeypatch.setattr("price_radar_http.PinnedHTTPSClient", lambda **limits: PinnedHTTPSClient(
        resolver=lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        connector=lambda *_args, **_kwargs: transport, ssl_context=transport, **limits,
    ))
    with factory() as db:
        station = RelayStation(name="Slow model", base_url="https://api.example.com/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        result = probe_relay(db, station, usage_client=FakeClient())
        assert result.status == expected
        assert result.latency_ms == elapsed_ms
        assert result.first_token_ms == (16000 if expected == "healthy" else None)
        assert transport.closed


def test_rollup_excludes_old_samples_and_configuration_diagnostics(relay_api):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", monitor_enabled=True, monitor_revision=2, base_url="https://api.example.com/v1", probe_model="test-model", encrypted_api_key=encrypt_secret(KEY))
        db.add(station)
        db.flush()
        now = datetime.now(timezone.utc)
        for status, age, revision in [("healthy", 1, 2), ("timeout", 2, 2), ("credential_error", 3, 2), ("unhealthy", 25, 2), ("unhealthy", 1, 1)]:
            db.add(RelayProbeResult(station_id=station.id, revision=revision, status=status, latency_ms=10, checked_at=now - timedelta(hours=age)))
        db.commit()
        health = relay_health(db, station)
        assert health.success_rate_24h == 50
        assert health.sample_count_24h == 2 and health.diagnostic_count_24h == 1
        assert health.availability_7d == 33.33 and health.sample_count_7d == 3
        assert [sample.status for sample in health.recent_samples] == ["unhealthy", "credential_error", "timeout", "healthy"]
        assert all(sample.checked_at.tzinfo is not None for sample in health.recent_samples)
        configure_relay(db, station, {"probe_model": "new-model"})
        assert relay_health(db, station).sample_count_24h == 0
        assert relay_health(db, station).recent_samples == []


def test_public_recent_samples_are_bounded_chronological_and_contain_no_credentials(relay_api):
    client, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Sample station", is_enabled=True, review_status="approved", monitor_enabled=True, monitor_revision=1, probe_model="test-model")
        db.add(station)
        db.flush()
        now = datetime.now(timezone.utc)
        for age in range(70):
            db.add(RelayProbeResult(station_id=station.id, revision=1, status="healthy" if age % 2 else "timeout", latency_ms=age, checked_at=now - timedelta(minutes=age)))
        db.commit()
    public = client.get("/api/v1/relays").json()["items"][0]["health"]
    samples = public["recent_samples"]
    assert public["sample_count_24h"] == 70
    assert len(samples) == 60
    assert [sample["latency_ms"] for sample in samples] == list(range(59, -1, -1))
    assert all(set(sample) == {"checked_at", "status", "latency_ms"} for sample in samples)
    assert all(sample["checked_at"].endswith("Z") for sample in samples)


def test_health_keeps_last_check_when_24h_window_is_empty(relay_api):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Test", monitor_enabled=True, monitor_revision=1)
        db.add(station)
        db.flush()
        db.add(RelayProbeResult(station_id=station.id, revision=1, status="healthy", latency_ms=20, checked_at=datetime.now(timezone.utc) - timedelta(hours=25)))
        db.commit()
        health = relay_health(db, station)
        assert health.status == "stale" and health.checked_at is not None
        assert health.sample_count_24h == 0 and health.success_rate_24h is None


def test_metric_rollups_use_own_windows_known_usage_and_current_revision(relay_api):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Metrics", monitor_enabled=True, monitor_revision=2)
        db.add(station)
        db.flush()
        now = datetime.now(timezone.utc)
        # Cache ratio is token weighted: (50 + 300) / (100 + 400).
        for age, status, total, cached, first, revision in [
            (1, "healthy", 100, 50, 100, 2),
            (2, "healthy", 400, 300, 300, 2),
            (3, "healthy", None, None, None, 2),
            (4, "timeout", 1000, 1000, 1, 2),
            (5, "config_error", 1000, 1000, 1, 2),
            (25, "unhealthy", None, None, None, 2),
            (26, "healthy", 1000, 1000, 1, 2),
            (169, "unhealthy", None, None, None, 2),
            (1, "unhealthy", 1000, 1000, 1, 1),
        ]:
            db.add(RelayProbeResult(station_id=station.id, revision=revision, checked_at=now-timedelta(hours=age), status=status, latency_ms=500, connect_latency_ms=25, first_token_ms=first, input_tokens=total, cached_input_tokens=cached))
        db.commit()
        health = relay_health(db, station)
        assert health.sample_count_24h == 4 and health.success_rate_24h == 75
        assert health.sample_count_7d == 6 and health.availability_7d == 66.67
        assert health.diagnostic_count_7d == 1
        assert health.cache_hit_rate_24h == 70 and health.cache_sample_count_24h == 2
        assert health.first_token_p50_ms == 200 and health.first_token_sample_count_24h == 2
        assert health.connect_latency_ms == 25
        assert len(health.recent_samples) == 7


@pytest.mark.parametrize("truncated", [False, True])
def test_streaming_probe_persists_measured_timings_and_usage_only(relay_api, monkeypatch, truncated):
    from price_radar_http import PinnedResponse

    _, factory = relay_api
    clock = [100.0]
    monkeypatch.setattr("app.services.relay_monitor.time.monotonic", lambda: clock[0])

    class StreamingClient(FakeClient):
        def post_json(self, url, body, *, headers, accept, on_chunk):
            assert accept == "text/event-stream"
            assert body["stream"] is True and body["stream_options"]["include_usage"] is True
            clock[0] += .01
            on_chunk(b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n')
            clock[0] += .12
            on_chunk(b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n')
            clock[0] += .1
            tail = b'data: {"choices":[],"usage":{"prompt_tokens":100,"prompt_tokens_details":{"cached_tokens":25}}}\n\ndata: [DONE]\n\n'
            if truncated:
                tail += b'data: {"error":{"message":"failed"}}\n'
            on_chunk(tail)
            return PinnedResponse(200, {"content-type": "text/event-stream; charset=utf-8"}, tail, 12)

    with factory() as db:
        station = RelayStation(name="Streaming", base_url="https://api.example.com/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        result = probe_relay(db, station, client=StreamingClient())
        if truncated:
            assert result.status == "invalid_response"
            assert result.first_token_ms is None and result.cached_input_tokens is None
            return
        assert result.status == "healthy"
        assert result.connect_latency_ms == 12 and result.first_token_ms == 130
        assert result.latency_ms == 230
        assert result.input_tokens == 100 and result.cached_input_tokens == 25
        assert KEY not in relay_health(db, station).model_dump_json()


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize(("counter_updates", "expected", "after_error", "direct_cache", "lag"), [
    ({"input_tokens": 112}, 0, None, None, False),
    ({"input_tokens": 102, "cache_read_tokens": 30}, 10, None, None, False),
    ({"input_tokens": 112, "requests": 12}, None, None, None, False),
    ({"input_tokens": 113}, None, None, None, False),
    ({"input_tokens": 112}, None, TimeoutError("private upstream error"), None, False),
    ({"input_tokens": 112}, 5, None, 5, False),
    ({"input_tokens": 112}, 0, None, None, True),
])
def test_sparse_usage_fallback_only_attributes_this_probe_and_keeps_model_timings(
    relay_api, monkeypatch, streaming, counter_updates, expected, after_error, direct_cache, lag,
):
    from price_radar_http import PinnedResponse

    _, factory = relay_api
    clock = [100.0]
    monkeypatch.setattr("app.services.relay_monitor.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.services.relay_monitor.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    baseline = {"requests": 10, "input_tokens": 100, "cache_read_tokens": 20, "cache_creation_tokens": 0}
    snapshots = [baseline]
    if lag:
        snapshots.append(baseline)
    snapshots.append({**baseline, "requests": 11, **counter_updates})

    class Accounting:
        calls = 0

        def get(self, url, *, headers, accept):
            assert url == "https://api.example.com/proxy/v1/usage"
            assert headers == {"Authorization": "Bearer " + KEY}
            clock[0] += 2  # Supplemental requests must not affect model latency.
            self.calls += 1
            if self.calls > 1 and after_error:
                raise after_error
            return PinnedResponse(200, {}, json.dumps({"usage": {"total": snapshots.pop(0)}}).encode())

    class Completion:
        def post_json(self, url, body, *, headers, accept, on_chunk):
            clock[0] += .13
            on_chunk(b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\n')
            clock[0] += .1
            usage = {"prompt_tokens": 12}
            if direct_cache is not None:
                usage["prompt_tokens_details"] = {"cached_tokens": direct_cache}
            if not streaming:
                return PinnedResponse(200, {"content-type": "application/json"}, json.dumps({
                    "choices": [{"message": {"content": "OK"}}], "usage": usage,
                }).encode(), 12)
            on_chunk(b"data: " + json.dumps({"choices": [], "usage": usage}).encode() + b"\n\ndata: [DONE]\n\n")
            return PinnedResponse(200, {"content-type": "text/event-stream"}, b"", 12)

    with factory() as db:
        station = RelayStation(name="Sparse usage", base_url="https://api.example.com/proxy/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        accounting = Accounting()
        result = probe_relay(db, station, client=Completion(), usage_client=accounting)
        assert result.status == "healthy"
        assert result.input_tokens == 12 and result.cached_input_tokens == expected
        assert result.latency_ms == 230 and result.first_token_ms == (130 if streaming else None) and result.connect_latency_ms == 12
        assert accounting.calls == (1 if direct_cache is not None else 3 if lag else 2)
        health = relay_health(db, station)
        assert health.cache_sample_count_24h == (0 if expected is None else 1)
        assert health.cache_hit_rate_24h == (None if expected is None else round(expected / 12 * 100, 2))
        assert KEY not in health.model_dump_json()


def test_consecutive_sparse_probes_each_collect_their_own_cache_sample(relay_api):
    from price_radar_http import PinnedResponse

    _, factory = relay_api

    class Accounting:
        calls = 0

        def get(self, url, *, headers, accept):
            requests = (self.calls + 1) // 2
            self.calls += 1
            return PinnedResponse(200, {}, json.dumps({"usage": {"total": {
                "requests": requests, "input_tokens": requests * 12,
                "cache_read_tokens": 0, "cache_creation_tokens": 0,
            }}}).encode())

    with factory() as db:
        station = RelayStation(name="Consecutive", base_url="https://api.example.com/v1", probe_model="test-model", monitor_enabled=True)
        configure_relay(db, station, {}, SecretStr(KEY))
        db.add(station)
        db.commit()
        accounting = Accounting()
        completion = FakeClient(body={"choices": [{"message": {"content": "OK"}}], "usage": {"prompt_tokens": 12}})
        for _ in range(3):
            result = probe_relay(db, station, client=completion, usage_client=accounting)
            assert result.status == "healthy" and result.cached_input_tokens == 0
        assert accounting.calls == 6 and len(completion.calls) == 3
        health = relay_health(db, station)
        assert health.cache_sample_count_24h == 3 and health.cache_hit_rate_24h == 0


def test_worker_claims_once_and_never_probes_unapproved_stations(relay_api, monkeypatch):
    client, factory = relay_api
    station_id = client.post("/api/v1/relay-requests", json=payload()).json()["request_id"]
    fake = FakeClient()
    monkeypatch.setattr("price_radar_http.PinnedHTTPSClient", lambda **kwargs: fake)
    run_due_probes(factory)
    assert fake.calls == []
    client.patch(f"/api/v1/admin/relays/{station_id}", headers=ADMIN, json={"review_status": "approved", "is_enabled": True})
    run_due_probes(factory)
    run_due_probes(factory)
    assert len(fake.calls) == 1
    assert fake.model_calls == []  # Metadata sync has an independent loop.
    assert client.post(f"/api/v1/admin/relays/{station_id}/probe", headers=ADMIN).status_code == 409
    with factory() as db:
        assert len(list(db.scalars(select(RelayProbeResult)))) == 1
        assert db.get(RelayStation, station_id).model_catalog == {}


def test_admin_can_replace_unreadable_key(relay_api):
    client, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Unreadable", encrypted_api_key="enc:v1:invalid", monitor_revision=3)
        db.add(station)
        db.commit()
        station_id = station.id
    response = client.patch(f"/api/v1/admin/relays/{station_id}", headers=ADMIN, json={"api_key": KEY})
    assert response.status_code == 200, response.text
    with factory() as db:
        station = db.get(RelayStation, station_id)
        assert decrypt_secret(station.encrypted_api_key) == KEY
        assert station.monitor_revision == 4


def test_configuration_change_invalidates_old_claim_without_duplicate_new_probe(relay_api):
    client, factory = relay_api
    station_id = client.post("/api/v1/relay-requests", json=payload()).json()["request_id"]
    client.patch(f"/api/v1/admin/relays/{station_id}", headers=ADMIN, json={"review_status": "approved", "is_enabled": True})
    with factory() as worker:
        old_target = claim_probe(worker, station_id)
        assert old_target is not None
        with factory() as editor:
            configure_relay(editor, editor.get(RelayStation, station_id), {"probe_model": "replacement-model"})
            editor.commit()
        new_target = claim_probe(worker, station_id)
        assert new_target is not None and new_target.monitor_revision != old_target.monitor_revision
        assert old_target.probe_model == "test-model"
        fake = FakeClient()
        assert probe_relay(worker, old_target, client=fake) is None
        assert probe_relay(worker, new_target, client=fake).status == "healthy"
        assert len(fake.calls) == 1 and fake.calls[0][1]["model"] == "replacement-model"
        assert claim_probe(worker, station_id) is None


def test_stale_admin_objects_receive_distinct_configuration_revisions(relay_api):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Concurrent edits", monitor_revision=1)
        db.add(station)
        db.commit()
        station_id = station.id
    with factory() as first, factory() as second:
        first_station = first.get(RelayStation, station_id)
        second_station = second.get(RelayStation, station_id)
        configure_relay(first, first_station, {"probe_model": "first-model"})
        first.commit()
        configure_relay(second, second_station, {"probe_model": "second-model"})
        second.commit()
        assert first_station.monitor_revision == 2
        assert second_station.monitor_revision == 3


def test_explicit_key_replacement_advances_revision_even_when_editor_has_stale_key(relay_api):
    _, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Concurrent key edits", monitor_revision=1, encrypted_api_key=encrypt_secret(KEY))
        db.add(station)
        db.commit()
        station_id = station.id
    with factory() as first, factory() as second:
        a = first.get(RelayStation, station_id)
        b = second.get(RelayStation, station_id)
        configure_relay(first, a, {}, SecretStr("replacement-key"))
        first.commit()
        configure_relay(second, b, {}, SecretStr(KEY))
        second.commit()
        assert b.monitor_revision == 3
        assert decrypt_secret(b.encrypted_api_key) == KEY
