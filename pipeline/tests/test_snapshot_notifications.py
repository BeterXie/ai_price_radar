from __future__ import annotations

import json
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

    def capture(events, db_session, *, snapshot_id, alert_report):
        snapshot = db_session.get(CatalogSnapshot, snapshot_id)
        assert snapshot.published_at is not None
        assert (tmp_path / "v1" / "snapshots" / f"{snapshot_id}.json").is_file()
        assert json.loads((tmp_path / "alerts-latest.json").read_text(encoding="utf-8")) == alert_report
        assert alert_report["snapshot_id"] == snapshot_id
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


def test_latest_report_is_replaced_even_without_changes_and_no_alert_history_is_saved(notification_run, tmp_path):
    db, _ = notification_run
    first = publish_sources(db, [SourceSpec("merchant-json", "team")])
    assert json.loads((tmp_path / "alerts-latest.json").read_text(encoding="utf-8"))["snapshot_id"] == first.snapshot_id
    second = publish_sources(db, [SourceSpec("merchant-json", "team")])
    latest = json.loads((tmp_path / "alerts-latest.json").read_text(encoding="utf-8"))
    assert latest["snapshot_id"] == second.snapshot_id
    assert latest["drops"] == latest["rises"] == []
    assert not (tmp_path / "v1" / "alerts").exists()


def test_report_export_failure_does_not_send_dead_links(notification_run, monkeypatch):
    import export_alerts
    db, sent = notification_run
    def fail(*args, **kwargs):
        raise OSError("report write failed")
    monkeypatch.setattr(export_alerts, "export_snapshot_alerts", fail)
    with pytest.raises(SnapshotExportError):
        publish_sources(db, [SourceSpec("merchant-json", "team")])
    assert sent == []


def test_price_transition_is_in_latest_report_before_dispatch(notification_run, monkeypatch, tmp_path):
    db, sent = notification_run
    original_loader = CONNECTORS["merchant-json"]
    price = ["20.00"]
    def loader(source):
        for row in original_loader(source):
            yield {**row, "listed_price": price[0]}
    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)
    publish_sources(db, [SourceSpec("merchant-json", "team")])
    price[0] = "18.00"
    latest = publish_sources(db, [SourceSpec("merchant-json", "team")])
    report = json.loads((tmp_path / "alerts-latest.json").read_text(encoding="utf-8"))
    assert report["snapshot_id"] == latest.snapshot_id
    assert len(report["drops"]) == 1
    assert report["drops"][0]["price"] == "18.00"
    assert report["drops"][0]["old_price"] == "20.00"
    assert len(sent[-1][1]) == 1


def test_superseded_report_cannot_overwrite_latest_or_authorize_notifications(notification_run, tmp_path):
    from export_alerts import export_snapshot_alerts
    db, _ = notification_run
    old = publish_sources(db, [SourceSpec("merchant-json", "team")])
    new = publish_sources(db, [SourceSpec("merchant-json", "team")])
    assert export_snapshot_alerts(db, old.snapshot_id, [], output_dir=tmp_path) is None
    assert json.loads((tmp_path / "alerts-latest.json").read_text(encoding="utf-8"))["snapshot_id"] == new.snapshot_id
