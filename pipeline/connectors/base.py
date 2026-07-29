from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol


class SourceConnector(Protocol):
    name: str

    def load_records(self, source: str | Path) -> Iterable[dict[str, Any]]:
        """Yield records accepted by pipeline.common.upsert_offer."""


REQUIRED_FIELDS = {"token", "product_name", "product_url"}


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(field for field in REQUIRED_FIELDS if not str(record.get(field) or "").strip())
    if missing:
        raise ValueError(f"connector record missing fields: {', '.join(missing)}")
    return record
