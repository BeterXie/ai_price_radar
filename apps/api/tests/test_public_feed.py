import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import public_feed


@pytest.fixture
def client():
    return TestClient(app)


def test_latest_alert_feed_updates_and_missing_report_is_not_an_empty_success(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path))
    assert client.get("/data/alerts-latest.json").status_code == 404
    report_file = tmp_path / "alerts-latest.json"
    (tmp_path / "latest.json").write_text(json.dumps({"snapshot_id": 1}), encoding="utf-8")
    report_file.write_text(json.dumps({"snapshot_id": 1, "drops": []}), encoding="utf-8")
    first = client.get("/data/alerts-latest.json")
    assert first.status_code == 200
    assert "immutable" not in first.headers["Cache-Control"]
    assert client.get("/data/alerts-latest.json", headers={"If-None-Match": first.headers["etag"]}).status_code == 304
    report_file.write_text(json.dumps({"snapshot_id": 22, "drops": [{"offer_id": 5}]}), encoding="utf-8")
    (tmp_path / "latest.json").write_text(json.dumps({"snapshot_id": 22}), encoding="utf-8")
    updated = client.get("/data/alerts-latest.json", headers={"If-None-Match": first.headers["etag"]})
    assert updated.status_code == 200 and updated.json()["snapshot_id"] == 22


def test_latest_alert_feed_rejects_old_report_after_catalog_pointer_advances(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path))
    (tmp_path / "alerts-latest.json").write_text('{"snapshot_id": 1}', encoding="utf-8")
    (tmp_path / "latest.json").write_text('{"snapshot_id": 2}', encoding="utf-8")
    assert client.get("/data/alerts-latest.json").status_code == 503


@pytest.mark.skipif(sys.platform == "win32", reason="Windows denies replacing an open file; exercise POSIX publication in Linux CI")
def test_replacing_alert_file_after_open_cannot_mix_response_headers_and_body(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path))
    path = tmp_path / "alerts-latest.json"
    original = b'{"snapshot_id":1,"drops":[{"offer_id":5}]}'
    path.write_bytes(original)
    (tmp_path / "latest.json").write_text('{"snapshot_id":1}')
    real_fstat = public_feed.os.fstat
    replaced = [False]
    def replacing_fstat(fd):
        stat = real_fstat(fd)
        if not replaced[0]:
            replaced[0] = True
            temporary = tmp_path / "next.json"
            temporary.write_text('{"snapshot_id":2}')
            temporary.replace(path)
        return stat
    monkeypatch.setattr(public_feed.os, "fstat", replacing_fstat)
    response = client.get("/data/alerts-latest.json")
    assert response.status_code == 200 and response.content == original
    assert int(response.headers["content-length"]) == len(original)


def test_public_feed_endpoints(client, tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    snapshots_dir = data_dir / "v1" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    latest_data = {
        "schema_version": "price-radar.v1",
        "snapshot_id": "1234",
        "generated_at": "2026-09-15T10:00:00Z",
        "published_at": "2026-09-15T10:00:00Z",
        "stale": False,
        "ranking_policy_version": "available-non-shared-first.v1",
        "snapshot_url": "https://ai.pricememo.cn/data/v1/snapshots/1234.json",
        "product_count": 1,
    }
    (data_dir / "latest.json").write_text(json.dumps(latest_data), encoding="utf-8")

    snapshot_data = {
        **latest_data,
        "products": [
            {
                "id": 1,
                "slug": "chatgpt-plus",
                "display_name": "ChatGPT Plus",
                "currency": "CNY",
                "min_price": 120.0,
                "offer_count": 1,
                "in_stock_count": 1,
                "top_5_offers": [],
            }
        ],
    }
    (snapshots_dir / "1234.json").write_text(json.dumps(snapshot_data), encoding="utf-8")

    monkeypatch.setattr(public_feed, "_find_data_dir", lambda: data_dir)

    # 1. Test GET /data/latest.json
    res = client.get("/data/latest.json")
    assert res.status_code == 200
    assert res.json()["snapshot_id"] == "1234"
    etag = res.headers["ETag"]
    assert etag is not None

    # Test ETag 304
    res_cached = client.get("/data/latest.json", headers={"If-None-Match": etag})
    assert res_cached.status_code == 304

    # 2. Test GET /data/v1/snapshots/1234.json
    res_snap = client.get("/data/v1/snapshots/1234.json")
    assert res_snap.status_code == 200
    assert res_snap.json()["products"][0]["slug"] == "chatgpt-plus"
    assert "immutable" in res_snap.headers["Cache-Control"]

    # Test snapshot ETag 304
    snap_etag = res_snap.headers["ETag"]
    res_snap_cached = client.get("/data/v1/snapshots/1234.json", headers={"If-None-Match": snap_etag})
    assert res_snap_cached.status_code == 304

    # 3. Test 404 for missing snapshot
    res_404 = client.get("/data/v1/snapshots/9999.json")
    assert res_404.status_code == 404

    # Invalid characters are rejected rather than stripped into another ID.
    res_alias = client.get("/data/v1/snapshots/12.34.json")
    assert res_alias.status_code == 400


def test_configured_public_data_dir_never_falls_back(tmp_path: Path, monkeypatch):
    configured = tmp_path / "missing-shared-volume"
    monkeypatch.setenv(public_feed.PUBLIC_DATA_DIR_ENV, str(configured))

    assert public_feed._find_data_dir() == configured


def test_catalog_summary_feed_is_versioned_and_conditional(client, tmp_path, monkeypatch):
    monkeypatch.setenv(public_feed.PUBLIC_DATA_DIR_ENV, str(tmp_path))
    directory = tmp_path / "v1" / "catalogs"
    directory.mkdir(parents=True)
    data = {"schema_version": "price-radar.catalog.v1", "snapshot_id": 42, "items": []}
    (directory / "42.json").write_text(json.dumps(data), encoding="utf-8")
    response = client.get("/data/v1/catalogs/42.json")
    assert response.status_code == 200
    assert response.json() == data
    assert "immutable" in response.headers["cache-control"]
    assert client.get("/data/v1/catalogs/42.json", headers={"If-None-Match": response.headers["etag"]}).status_code == 304
    assert client.get("/data/v1/catalogs/43.json").status_code == 404
    assert client.get("/data/v1/catalogs/4.2.json").status_code == 400
