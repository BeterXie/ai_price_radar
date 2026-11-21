"""Publish only the latest alert report before its notifications are sent."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from common import CatalogSnapshot, import_lock
from app.services.alert_reports import build_alert_report, public_offer_prices


def export_snapshot_alerts(db, snapshot_id: int, events: list, *, output_dir: Path,
                           previous_snapshot_id: int | None = None) -> dict | None:
    output_dir = Path(output_dir)
    previous_prices = {}
    if previous_snapshot_id is not None:
        previous_path = output_dir / "v1" / "snapshots" / f"{previous_snapshot_id}.json"
        if previous_path.is_file():
            previous_prices = public_offer_prices(json.loads(previous_path.read_text(encoding="utf-8")))
        elif events:
            raise ValueError("Previous public snapshot is unavailable; cannot verify price changes")
    snapshot = json.loads((output_dir / "v1" / "snapshots" / f"{snapshot_id}.json").read_text(encoding="utf-8"))
    report = build_alert_report(snapshot, events, previous_prices=previous_prices)
    with import_lock(db, wait=True):
        current_id = db.scalar(select(CatalogSnapshot.id).where(CatalogSnapshot.published_at.is_not(None))
                               .order_by(CatalogSnapshot.id.desc()).limit(1))
        if current_id != snapshot_id:
            return None
        _write_json(output_dir / "alerts-latest.json", report)
    return report


def _write_json(path: Path, value: dict) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2)
    if len(content.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("Alert report exceeds the public 8 MiB limit")
    temporary = path.with_name(f".tmp_{path.name}_{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
