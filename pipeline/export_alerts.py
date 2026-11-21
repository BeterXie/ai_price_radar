"""Publish only the latest alert report before its notifications are sent."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from common import CatalogSnapshot, publication_lock
from app.services.alert_reports import build_alert_report, public_offer_prices


def prepare_snapshot_alerts(snapshot: dict, events: list, *, output_dir: Path,
                            previous_snapshot_id: int | None = None) -> dict:
    previous_prices = {}
    if events and previous_snapshot_id is not None:
        previous_path = output_dir / "v1" / "snapshots" / f"{previous_snapshot_id}.json"
        if previous_path.is_file():
            previous_prices = public_offer_prices(json.loads(previous_path.read_text(encoding="utf-8")))
        elif events:
            raise ValueError("Previous public snapshot is unavailable; cannot verify price changes")
    report = build_alert_report(snapshot, events, previous_prices=previous_prices)
    _encoded_report(report)
    return report


def export_snapshot_alerts(db, snapshot_id: int, events: list, *, output_dir: Path,
                           previous_snapshot_id: int | None = None, prepared_report: dict | None = None) -> dict | None:
    output_dir = Path(output_dir)
    with publication_lock(db):
        current_id = db.scalar(select(CatalogSnapshot.id).where(CatalogSnapshot.published_at.is_not(None))
                               .order_by(CatalogSnapshot.id.desc()).limit(1))
        if current_id != snapshot_id:
            return None
        report = prepared_report
        if report is None:
            snapshot = json.loads((output_dir / "v1" / "snapshots" / f"{snapshot_id}.json").read_text(encoding="utf-8"))
            report = prepare_snapshot_alerts(snapshot, events, output_dir=output_dir, previous_snapshot_id=previous_snapshot_id)
        _write_json(output_dir / "alerts-latest.json", report)
    return report


def _encoded_report(value: dict) -> str:
    content = json.dumps(value, ensure_ascii=False, indent=2)
    if len(content.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("Alert report exceeds the public 8 MiB limit")
    return content


def _write_json(path: Path, value: dict) -> None:
    content = _encoded_report(value)
    temporary = path.with_name(f".tmp_{path.name}_{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
