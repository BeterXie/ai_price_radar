import json
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr
from app.models import RelayStation
from app.services.relay_models import CatalogResponseError, fetch_relay_models, run_due_model_syncs, sync_relay_models
from app.services.relay_monitor import ProbeTarget, configure_relay
from test_relay_monitor import ADMIN, KEY, payload, relay_api


@pytest.fixture(autouse=True)
def group_sync_is_tested_separately(monkeypatch):
    monkeypatch.setattr("app.services.relay_groups.fetch_group_catalog", lambda *_args, **_kwargs: {
        "status": "unsupported", "checked_at": "2026-01-01T00:00:00+00:00",
    })


def target(protocol="openai", base="https://api.example.com/prefix"):
    return ProbeTarget(1, 1, base, protocol, "test-model", KEY)


class ModelClient:
    def __init__(self, *pages, status=200, error=None):
        self.pages = list(pages)
        self.status = status
        self.error = error
        self.calls = []

    def get(self, url, *, accept, headers):
        from price_radar_http import PinnedResponse
        self.calls.append((url, headers))
        if self.error:
            raise self.error
        return PinnedResponse(self.status, {}, json.dumps(self.pages.pop(0) if self.pages else {}).encode())


def test_openai_models_use_credential_header_and_only_publish_metadata():
    client = ModelClient({"data": [
        {"id": "gpt-z", "display_name": "GPT Z", "owned_by": "Provider", "description": "A model", "context_length": 1000, "max_output_tokens": 50, "private_key": KEY},
        {"id": "gpt-a"}, {"id": "gpt-z", "display_name": "GPT Z", "owned_by": "Provider", "description": "A model", "context_length": 1000, "max_output_tokens": 50},
    ]})
    models, truncated = fetch_relay_models(target(), KEY, client=client)
    assert [m["id"] for m in models] == ["gpt-a", "gpt-z"]
    assert models[1]["description"] == "A model"
    assert models[1]["context_token_limit"] == 1000 and models[1]["output_token_limit"] == 50
    assert models[1]["input_token_limit"] is None
    assert KEY not in json.dumps(models)
    assert not truncated
    url, headers = client.calls[0]
    assert url == "https://api.example.com/prefix/v1/models" and KEY not in url
    assert headers == {"Authorization": "Bearer " + KEY}


@pytest.mark.parametrize("protocol", ["anthropic", "gemini"])
def test_paginated_models_keep_credentials_on_configured_host(protocol):
    cursor = "next /?&=page"
    if protocol == "gemini":
        pages = [{"models": [{"name": "models/first", "displayName": "First", "inputTokenLimit": 1000, "outputTokenLimit": 30, "supportedGenerationMethods": ["generateContent"]}], "nextPageToken": cursor}, {"models": [{"name": "models/second"}]}]
    else:
        pages = [{"data": [{"id": "first", "display_name": "First"}], "has_more": True, "last_id": cursor}, {"data": [{"id": "second"}], "has_more": False}]
    client = ModelClient(*pages)
    models, truncated = fetch_relay_models(target(protocol), KEY, client=client)
    assert [m["id"] for m in models] == ["first", "second"] and not truncated
    second_url, headers = client.calls[1]
    assert urlsplit(second_url).netloc == "api.example.com" and KEY not in second_url
    assert parse_qs(urlsplit(second_url).query)["pageToken" if protocol == "gemini" else "after_id"] == [cursor]
    assert headers["x-goog-api-key" if protocol == "gemini" else "x-api-key"] == KEY
    if protocol == "gemini":
        assert models[0]["capabilities"] == ["generateContent"]
        assert models[0]["input_token_limit"] == 1000


@pytest.mark.parametrize("page", [
    {"data": [{"id": KEY}]}, {"data": [{"name": "not-an-openai-id"}]},
    {"data": "invalid"}, {"error": {"message": KEY}},
])
def test_invalid_or_secret_echoed_models_are_not_cached(page):
    with pytest.raises(CatalogResponseError):
        fetch_relay_models(target(), KEY, client=ModelClient(page))


def test_metadata_that_echoes_a_key_is_omitted():
    models, _ = fetch_relay_models(target(), KEY, client=ModelClient({"data": [{"id": "safe", "description": "key=" + KEY, "owned_by": KEY}]}))
    assert models[0]["description"] == models[0]["provider"] == ""


def test_optional_untrusted_metadata_is_normalized_before_public_serialization():
    from app.schemas import RelayModelCatalog

    models, _ = fetch_relay_models(target(), KEY, client=ModelClient({"data": [{
        "id": "model", "display_name": None, "description": {"unexpected": True},
        "owned_by": None, "max_input_tokens": True, "supportedGenerationMethods": None,
    }]}))
    public = RelayModelCatalog.model_validate({"status": "ok", "models": models})
    model = public.models[0]
    assert model.name == "model" and model.description == model.provider == ""
    assert model.capabilities == [] and model.input_token_limit is None


def test_pagination_loops_fail_and_model_count_is_bounded(monkeypatch):
    page = {"models": [{"name": "models/first"}], "nextPageToken": "repeat"}
    with pytest.raises(CatalogResponseError):
        fetch_relay_models(target("gemini"), KEY, client=ModelClient(page, page))
    monkeypatch.setattr("app.services.relay_models.MAX_MODELS", 2)
    models, truncated = fetch_relay_models(target(), KEY, client=ModelClient({"data": [{"id": f"model-{n}"} for n in range(3)]}))
    assert len(models) == 2 and truncated


def configured_station(db):
    station = RelayStation(name="Models", is_enabled=True, review_status="approved")
    configure_relay(db, station, {"base_url": "https://api.example.com/v1", "probe_model": "test-model"}, SecretStr(KEY))
    db.add(station)
    db.commit()
    return station, ProbeTarget(station.id, station.monitor_revision, station.base_url, station.probe_protocol, station.probe_model, station.encrypted_api_key)


def test_sync_failure_keeps_last_catalog_and_config_change_clears_it(relay_api):
    _, factory = relay_api
    with factory() as db:
        station, snapshot = configured_station(db)
        assert sync_relay_models(db, snapshot, client=ModelClient({"data": [{"id": "live-model"}]}))
        previous = dict(station.model_catalog)
        assert sync_relay_models(db, snapshot, client=ModelClient(error=TimeoutError(KEY)))
        assert station.model_catalog["status"] == "timeout"
        assert station.model_catalog["models"] == previous["models"]
        assert station.model_catalog["synced_at"] == previous["synced_at"]
        assert KEY not in json.dumps(station.model_catalog)
        configure_relay(db, station, {"base_url": "https://other.example.com/v1"})
        db.commit()
        assert station.model_catalog == {}
        old_client = ModelClient({"data": [{"id": "old-model"}]})
        assert not sync_relay_models(db, snapshot, client=old_client) and not old_client.calls


def test_inflight_catalog_is_discarded_after_configuration_changes(relay_api):
    _, factory = relay_api
    with factory() as db:
        station, snapshot = configured_station(db)

        class EditingClient(ModelClient):
            def get(self, *args, **kwargs):
                with factory() as editor:
                    configure_relay(editor, editor.get(RelayStation, station.id), {"probe_model": "replacement"})
                    editor.commit()
                return super().get(*args, **kwargs)

        assert not sync_relay_models(db, snapshot, client=EditingClient({"data": [{"id": "stale-model"}]}))
        assert db.get(RelayStation, station.id).model_catalog == {}


def test_admin_sync_requires_approval_and_public_catalog_excludes_credentials(relay_api, monkeypatch):
    client, factory = relay_api
    station_id = client.post("/api/v1/relay-requests", json=payload()).json()["request_id"]
    path = f"/api/v1/admin/relays/{station_id}/models/sync"
    fake = ModelClient({"data": [{"id": "live-model", "display_name": "Live model"}]})
    monkeypatch.setattr("price_radar_http.PinnedHTTPSClient", lambda **_kwargs: fake)
    assert client.post(path).status_code == 401
    assert client.post(path, headers=ADMIN).status_code == 409 and not fake.calls
    client.patch(f"/api/v1/admin/relays/{station_id}", headers=ADMIN, json={"review_status": "approved", "is_enabled": True})
    response = client.post(path, headers=ADMIN)
    assert response.status_code == 200 and response.json()["model_catalog"]["status"] == "ok"
    public = client.get("/api/v1/relays")
    assert public.json()["items"][0]["model_catalog"]["models"][0]["id"] == "live-model"
    assert KEY not in public.text and "base_url" not in public.text and "encrypted_api_key" not in public.text


@pytest.mark.parametrize("intervention", ["config", "newer_sync"])
def test_catalog_compare_and_swap_rejects_changes_after_final_read(relay_api, monkeypatch, intervention):
    _, factory = relay_api
    with factory() as db:
        station, snapshot = configured_station(db)
        original_execute = db.execute
        changed = False

        def execute(statement, *args, **kwargs):
            nonlocal changed
            if getattr(statement, "is_update", False) and not changed:
                changed = True
                with factory() as other:
                    if intervention == "config":
                        configure_relay(other, other.get(RelayStation, station.id), {"probe_model": "replacement"})
                        other.commit()
                    else:
                        assert sync_relay_models(other, snapshot, client=ModelClient({"data": [{"id": "newer-model"}]}))
            return original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(db, "execute", execute)
        assert not sync_relay_models(db, snapshot, client=ModelClient({"data": [{"id": "obsolete-model"}]}))
        current = db.get(RelayStation, station.id)
        if intervention == "config":
            assert current.model_catalog == {}
        else:
            assert current.model_catalog["models"][0]["id"] == "newer-model"


def test_catalog_sync_runs_hourly_without_completion_monitoring(relay_api, monkeypatch):
    _, factory = relay_api
    with factory() as db:
        station, _ = configured_station(db)
        assert not station.monitor_enabled
    fake = ModelClient({"data": [{"id": "discovered-model"}]})
    monkeypatch.setattr("price_radar_http.PinnedHTTPSClient", lambda **_kwargs: fake)
    run_due_model_syncs(factory)
    run_due_model_syncs(factory)
    assert len(fake.calls) == 1
    with factory() as db:
        assert db.get(RelayStation, station.id).model_catalog["models"][0]["id"] == "discovered-model"


def test_editor_with_empty_cache_still_clears_a_concurrent_sync(relay_api):
    _, factory = relay_api
    with factory() as editor:
        station, snapshot = configured_station(editor)
        assert station.model_catalog == {}
        with factory() as syncer:
            assert sync_relay_models(syncer, snapshot, client=ModelClient({"data": [{"id": "old-key-model"}]}))
        # The editor still holds {}, so normal dirty checking would omit reset.
        configure_relay(editor, station, {"base_url": "https://changed.example.com/v1"})
        editor.commit()
    with factory() as db:
        assert db.get(RelayStation, station.id).model_catalog == {}


def test_shutdown_signal_prevents_starting_more_stations(relay_api, monkeypatch):
    from threading import Event

    _, factory = relay_api
    with factory() as db:
        configured_station(db)
        configured_station(db)
    stop = Event()
    calls = []

    def sync_one(_db, snapshot):
        calls.append(snapshot.id)
        stop.set()

    monkeypatch.setattr("app.services.relay_models.sync_relay_models", sync_one)
    run_due_model_syncs(factory, stop)
    assert len(calls) == 1


def test_cancelled_loop_signals_its_background_worker(monkeypatch):
    import asyncio
    from app.services.relay_models import relay_model_sync_loop

    async def scenario():
        captured = []

        async def run_thread(_fn, _factory, stop):
            captured.append(stop)
            await asyncio.Future()

        monkeypatch.setattr("app.services.relay_models.asyncio.to_thread", run_thread)
        task = asyncio.create_task(relay_model_sync_loop(None))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert captured[0].is_set()

    asyncio.run(scenario())
