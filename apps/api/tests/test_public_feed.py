import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import public_feed


@pytest.fixture
def client():
    return TestClient(app)


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
