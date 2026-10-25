import json

import pytest
from price_radar_http import PinnedResponse

from app.models import RelayStation
from app.services.relay_groups import fetch_group_catalog
from app.services.relay_models import sync_relay_models
from test_relay_models import ModelClient, configured_station, target
from test_relay_monitor import ADMIN, KEY, payload, relay_api


class GroupClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, accept, headers):
        self.calls.append((url, headers))
        status, body = self.responses.pop(0)
        return PinnedResponse(status, {}, json.dumps(body).encode())


def test_key_billing_reads_multiple_real_groups_without_account_details():
    fake = GroupClient((200, {"groups": [
        {"group_id": 24, "group_name": "GPT Enterprise", "group_rate_multiplier": .25, "effective_rate_multiplier": .3, "balance": 100, "api_key": KEY},
        {"group_id": 6, "group_name": "GPT PRO", "group_rate_multiplier": 0},
    ], "balance": 500, "api_key": KEY}))
    result = fetch_group_catalog(target(base="https://api.example.com/prefix/v1"), KEY, client=fake)
    assert result["status"] == "ok" and result["source"] == "key_billing"
    assert result["groups"][0] == {"id": "24", "name": "GPT Enterprise", "ratio": .25, "effective_ratio": .3, "description": "", "models": None}
    assert result["groups"][1]["ratio"] == 0
    assert "balance" not in json.dumps(result) and KEY not in json.dumps(result)
    assert fake.calls == [("https://api.example.com/prefix/v1/sub2api/billing", {"Authorization": "Bearer " + KEY})]


def test_single_key_group_does_not_invent_a_name_or_model_scope():
    fake = GroupClient((200, {"group_rate_multiplier": .18, "effective_rate_multiplier": .18}))
    group = fetch_group_catalog(target(), KEY, client=fake)["groups"][0]
    assert group["name"] == "当前密钥分组" and group["ratio"] == .18 and group["models"] is None


def test_public_new_api_groups_use_declared_model_membership_and_no_auth_header():
    fake = GroupClient((404, {}), (200, {"group_ratio": {"vip": .5, "free": 0, "other": None}, "data": [
        {"model_name": "model-a", "enable_groups": ["vip", "free"]},
        {"model_name": "model-b", "enable_groups": ["vip"]},
    ]}))
    result = fetch_group_catalog(target(), KEY, client=fake)
    assert result["source"] == "public_pricing" and result["status"] == "ok"
    assert result["groups"][0]["models"] == ["model-a", "model-b"]
    assert result["groups"][1]["models"] == ["model-a"]
    assert result["groups"][2]["models"] == [] and result["groups"][2]["ratio"] is None
    assert fake.calls[1] == ("https://api.example.com/prefix/api/pricing", {})


def test_omitted_membership_is_unknown_and_unsafe_metadata_is_omitted():
    fake = GroupClient((404, {}), (200, {"group_ratio": {"vip": {"GroupRatio": -1, "DisplayName": KEY, "Description": KEY}}, "data": [{"model_name": "model-a"}]}))
    group = fetch_group_catalog(target(), KEY, client=fake)["groups"][0]
    assert group["models"] is None and group["ratio"] is None
    assert group["name"] == "vip" and group["description"] == ""


@pytest.mark.parametrize("status,expected", [(401, "credential_error"), (500, "upstream_error")])
def test_billing_error_is_not_misrepresented_as_success(status, expected):
    fake = GroupClient((status, {"error": KEY}))
    result = fetch_group_catalog(target(), KEY, client=fake)
    assert result["status"] == expected and "groups" not in result and len(fake.calls) == 1


@pytest.mark.parametrize("body", [
    {"groups": None}, {"groups": {}},
    {"groups": [{"group_id": 10 ** 125, "group_name": "Too long", "group_rate_multiplier": .1}]},
])
def test_invalid_group_response_cannot_overwrite_valid_cache(relay_api, body):
    _, factory = relay_api
    with factory() as db:
        station, snapshot = configured_station(db)
        assert sync_relay_models(db, snapshot, client=ModelClient({"data": []}), group_client=GroupClient((200, {"group_rate_multiplier": .12})))
        previous = station.model_catalog["group_catalog"]
        assert sync_relay_models(db, snapshot, client=ModelClient({"data": []}), group_client=GroupClient((200, body)))
        current = station.model_catalog["group_catalog"]
        assert current["status"] == "invalid_response"
        assert current["groups"] == previous["groups"] and current["synced_at"] == previous["synced_at"]


def test_group_success_survives_model_failure_and_later_group_failure(relay_api):
    _, factory = relay_api
    with factory() as db:
        station, snapshot = configured_station(db)
        assert sync_relay_models(db, snapshot, client=ModelClient(error=TimeoutError()), group_client=GroupClient((200, {"group_rate_multiplier": .12})))
        saved = station.model_catalog["group_catalog"]
        assert saved["groups"][0]["ratio"] == .12 and station.model_catalog["status"] == "timeout"
        assert sync_relay_models(db, snapshot, client=ModelClient({"data": []}), group_client=GroupClient((500, {})))
        current = station.model_catalog["group_catalog"]
        assert current["status"] == "upstream_error" and current["synced_at"] == saved["synced_at"]
        assert current["groups"] == saved["groups"]


def test_submission_and_admin_can_manage_groups_without_monitor_revision_change(relay_api):
    client, factory = relay_api
    group = {"id": "vip", "name": "VIP", "ratio": .5, "models": ["a", "a", "b"]}
    response = client.post("/api/v1/relay-requests", json=payload(groups=[group]))
    assert response.status_code == 201, response.text
    station_id = response.json()["request_id"]
    with factory() as db:
        station = db.get(RelayStation, station_id)
        revision = station.monitor_revision
        assert station.groups[0]["models"] == ["a", "b"]
    path = f"/api/v1/admin/relays/{station_id}"
    changed = client.patch(path, headers=ADMIN, json={"groups": [{**group, "ratio": 0}], "review_status": "approved", "is_enabled": True})
    assert changed.status_code == 200 and changed.json()["groups"][0]["ratio"] == 0
    public = client.get("/api/v1/relays").json()["items"][0]
    assert public["groups"][0]["name"] == "VIP" and public["groups"][0]["ratio"] == 0
    with factory() as db:
        assert db.get(RelayStation, station_id).monitor_revision == revision
    assert client.patch(path, headers=ADMIN, json={"groups": [group, group]}).status_code == 422
    assert client.patch(path, headers=ADMIN, json={"groups": [{**group, "ratio": -1}]}).status_code == 422
    assert client.patch(path, headers=ADMIN, json={"groups": [{**group, "id": " "}]}).status_code == 422
    assert client.patch(path, headers=ADMIN, json={"groups": []}).json()["groups"] == []
