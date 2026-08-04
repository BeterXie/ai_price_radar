from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .base import validate_record


name = "ldxp"


def load_records(source: str | Path) -> Iterable[dict[str, Any]]:
    path = Path(source)
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(source_uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
        intake_id = "c.intake_id" if "intake_id" in candidate_columns else "NULL AS intake_id"
        intake_attempt_count = (
            "c.intake_attempt_count" if "intake_attempt_count" in candidate_columns else "NULL AS intake_attempt_count"
        )
        rows = conn.execute(
            f"""
            SELECT m.*, c.status AS shop_status, c.source_score, c.last_success_at,
                   c.consecutive_failures, c.scanned_at, {intake_id}, {intake_attempt_count}
            FROM matches m
            LEFT JOIN candidates c ON c.token = m.token
            ORDER BY m.collected_at
            """
        )
        for row in rows:
            record = dict(row)
            # v3.7.1 data minimization: never forward the upstream raw payload.
            record.pop("raw_json", None)
            record.pop("raw", None)
            record["source_platform"] = "ldxp"
            yield validate_record(record)
    finally:
        conn.close()
