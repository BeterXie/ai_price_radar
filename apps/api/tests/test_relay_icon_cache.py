import base64
from datetime import datetime, timedelta, timezone

from app.models import RelayStation
from app.services import relay_icons
from test_relay_icons import HOME, PNG
from test_relay_monitor import relay_api


def test_icon_survives_process_cache_loss_and_upstream_outage(relay_api, monkeypatch):
    from app.routers import public

    client, factory = relay_api
    icon = relay_icons.RelayIcon(PNG, "image/png")
    calls = []
    monkeypatch.setattr(public, "get_relay_icon", lambda url: calls.append(url) or icon)
    with factory() as db:
        station = RelayStation(name="Persistent icon", url=HOME, review_status="approved", is_enabled=True)
        db.add(station)
        db.commit()
        station_id = station.id
        updated_at = station.updated_at
    path = f"/api/v1/relays/{station_id}/icon"
    assert client.get(path).content == PNG
    assert calls == [HOME]
    with factory() as db:
        station = db.get(RelayStation, station_id)
        saved = dict(station.icon_cache)
        assert base64.b64decode(saved["body"]) == PNG
        assert station.updated_at.replace(tzinfo=None) == updated_at.replace(tzinfo=None)
    relay_icons._cache.clear()  # A replacement API process still has the DB cache.
    assert client.get(path).content == PNG and calls == [HOME]
    with factory() as db:
        station = db.get(RelayStation, station_id)
        station.icon_cache = {**saved, "synced_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
        db.commit()
    monkeypatch.setattr(public, "get_relay_icon", lambda _url: None)
    response = client.get(path)
    assert response.status_code == 200 and response.content == PNG
    assert "stale-if-error" in response.headers["cache-control"]
    monkeypatch.setattr(public, "get_relay_icon", lambda _url: (_ for _ in ()).throw(relay_icons.RelayIconBusy()))
    assert client.get(path).content == PNG
    public_data = client.get("/api/v1/relays").text
    assert "icon_cache" not in public_data and saved["body"] not in public_data
    with factory() as db:
        db.get(RelayStation, station_id).url = "https://replacement.example.com"
        db.commit()
    monkeypatch.setattr(public, "get_relay_icon", lambda _url: None)
    assert client.get(path).status_code == 404


def test_old_home_icon_cannot_overwrite_cache_after_website_edit(relay_api, monkeypatch):
    from app.routers import public

    client, factory = relay_api
    with factory() as db:
        station = RelayStation(name="Editing icon", url=HOME, review_status="approved", is_enabled=True)
        db.add(station)
        db.commit()
        station_id = station.id

    def fetch(_url):
        with factory() as editor:
            editor.get(RelayStation, station_id).url = "https://replacement.example.com"
            editor.commit()
        return relay_icons.RelayIcon(PNG, "image/png")

    monkeypatch.setattr(public, "get_relay_icon", fetch)
    assert client.get(f"/api/v1/relays/{station_id}/icon").status_code == 200
    with factory() as db:
        assert db.get(RelayStation, station_id).icon_cache == {}
