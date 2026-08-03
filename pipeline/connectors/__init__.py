from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

from . import dujiao_next, ldxp, merchant_json

Loader = Callable[[str | Path], Iterable[dict[str, Any]]]

CONNECTORS: dict[str, Loader] = {
    "dujiao-next": dujiao_next.load_records,
    "ldxp": ldxp.load_records,
    "merchant-json": merchant_json.load_records,
}


def get_connector(name: str) -> Loader:
    try:
        return CONNECTORS[name]
    except KeyError as exc:
        raise ValueError(f"unknown connector: {name}") from exc
