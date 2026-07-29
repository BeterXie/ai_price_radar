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
        rows = conn.execute(
            """
            SELECT m.*, c.status AS shop_status, c.source_score, c.last_success_at,
                   c.consecutive_failures, c.scanned_at
            FROM matches m
            LEFT JOIN candidates c ON c.token = m.token
            ORDER BY m.collected_at
            """
        )
        for row in rows:
            record = dict(row)
            record["source_platform"] = "ldxp"
            yield validate_record(record)
    finally:
        conn.close()
