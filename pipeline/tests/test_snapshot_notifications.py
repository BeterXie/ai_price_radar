from __future__ import annotations

import pytest

import export_snapshot
from app.services import notification_hub
from common import CatalogSnapshot, session_for
from connectors import CONNECTORS
from publish_catalog import SnapshotExportError, SourceImportError, SourceSpec, publish_sources


@pytest.fixture
def notification_run(monkeypatch, tmp_path):
    def loader(_source):
        yield {
            "token": "team-shop", "shop_name": "Team商家", "shop_url": "https://team.example",
            "source_platform": "merchant_json", "product_key": "team-5x",
            "product_name": "ChatGPT Team 5x 二车", "product_url": "https://team.example/goods/5x",
            "listed_price": "20.00", "currency": "CNY", "stock_count": 2, "product_status": "in_stock",
        }

    sent = []

    def capture(events, db_session, *, snapshot_id):
        snapshot = db_session.get(CatalogSnapshot, snapshot_id)
        assert snapshot.published_at is not None
        assert (tmp_path / "v1" / "snapshots" / f"{snapshot_id}.json").is_file()
        sent.append((snapshot_id, list(events)))

    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)
    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(notification_hub, "dispatch_price_changes", capture)
    db = session_for("sqlite://")
    try:
        yield db, sent
    finally:
        db.close()


def test_new_and_unchanged_snapshots_dispatch_after_public_feed_export(notification_run):
    db, sent = notification_run
    sources = [SourceSpec("merchant-json", "team")]
    first = publish_sources(db, sources)
    second = publish_sources(db, sources)
    assert sent == [(first.snapshot_id, []), (second.snapshot_id, [])]


def test_dry_run_does_not_dispatch(notification_run):
    db, sent = notification_run
    publish_sources(db, [SourceSpec("merchant-json", "team")], dry_run=True)
    assert sent == []


def test_export_failure_does_not_dispatch(notification_run, monkeypatch):
    db, sent = notification_run

    def fail_export(*args, **kwargs):
        raise OSError("export failed")

    monkeypatch.setattr(export_snapshot, "export_public_snapshot", fail_export)
    with pytest.raises(SnapshotExportError):
        publish_sources(db, [SourceSpec("merchant-json", "team")])
    assert sent == []


def test_failed_import_does_not_dispatch(notification_run, monkeypatch):
    db, sent = notification_run

    def fail_load(_source):
        raise ValueError("upstream failed")

    monkeypatch.setitem(CONNECTORS, "merchant-json", fail_load)
    with pytest.raises(SourceImportError):
        publish_sources(db, [SourceSpec("merchant-json", "team")])
    assert sent == []
