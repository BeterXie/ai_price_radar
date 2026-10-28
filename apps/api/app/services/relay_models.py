"""Cache only public model metadata returned to a relay's configured key."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from threading import Event
from urllib.parse import urlencode

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..models import RelayStation
from .credential_crypto import decrypt_secret
from .relay_monitor import ProbeTarget

MAX_MODELS = 2000
MAX_PAGES = 5
logger = logging.getLogger(__name__)


class CatalogResponseError(ValueError):
    def __init__(self, status: str):
        self.status = status


def _text(value: object, key: str, limit: int = 120) -> str:
    if not isinstance(value, str) or key in value:
        return ""
    return " ".join(value.split())[:limit]


def _limit(value: object) -> int | None:
    return value if type(value) is int and 0 < value <= 2_147_483_647 else None


def _model(row: object, protocol: str, key: str) -> dict | None:
    if not isinstance(row, dict):
        return None
    raw_id = row.get("name") if protocol == "gemini" else row.get("id")
    if not isinstance(raw_id, str) or len(raw_id) > 200:
        return None
    model_id = _text(raw_id, key, 200)
    if protocol == "gemini":
        model_id = model_id.removeprefix("models/")
    if not model_id:
        return None
    methods = row.get("supportedGenerationMethods", [])
    return {
        "id": model_id,
        "name": _text(row.get("display_name", row.get("displayName")), key) or model_id,
        "description": _text(row.get("description"), key, 1000),
        "provider": _text(row.get("owned_by", row.get("provider")), key),
        "context_token_limit": _limit(row.get("context_length")),
        "input_token_limit": _limit(row.get("inputTokenLimit", row.get("max_input_tokens"))),
        "output_token_limit": _limit(row.get("outputTokenLimit", row.get("max_output_tokens"))),
        "capabilities": list(dict.fromkeys(_text(item, key, 80) for item in methods if _text(item, key, 80)))[:20] if isinstance(methods, list) else [],
    }


def fetch_relay_models(target: ProbeTarget, key: str, *, client=None) -> tuple[list[dict], bool]:
    from price_radar_http import PinnedHTTPSClient

    base = target.base_url.rstrip("/")
    protocol = target.probe_protocol
    if protocol == "gemini":
        base = base if base.endswith(("/v1", "/v1beta")) else base + "/v1beta"
        headers = {"x-goog-api-key": key}
    else:
        base = base if base.endswith("/v1") else base + "/v1"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"} if protocol == "anthropic" else {"Authorization": "Bearer " + key}
    client = client or PinnedHTTPSClient(
        max_response_bytes=1024 * 1024, max_task_bytes=1024 * 1024,
        max_task_seconds=45, request_timeout=30,
    )
    cursor = ""
    seen_cursors = set()
    models: dict[str, dict] = {}
    for _ in range(MAX_PAGES):
        params = {"pageSize": "1000", **({"pageToken": cursor} if cursor else {})} if protocol == "gemini" else (
            {"limit": "1000", **({"after_id": cursor} if cursor else {})} if protocol == "anthropic" else {}
        )
        url = base + "/models" + ("?" + urlencode(params) if params else "")
        response = client.get(url, accept="application/json", headers=headers)
        if response.status_code in (401, 403):
            raise CatalogResponseError("credential_error")
        if not 200 <= response.status_code < 300:
            raise CatalogResponseError("unsupported" if response.status_code in (404, 405) else "upstream_error")
        payload = json.loads(response.body)
        if not isinstance(payload, dict) or payload.get("error"):
            raise CatalogResponseError("invalid_response")
        rows = payload.get("models" if protocol == "gemini" else "data")
        if not isinstance(rows, list):
            raise CatalogResponseError("invalid_response")
        for row in rows:
            model = _model(row, protocol, key)
            if model is None:
                raise CatalogResponseError("invalid_response")
            if model["id"] not in models and len(models) >= MAX_MODELS:
                return sorted(models.values(), key=lambda m: m["id"].casefold()), True
            models[model["id"]] = model
        next_cursor = payload.get("nextPageToken") if protocol == "gemini" else (
            payload.get("last_id") if protocol == "anthropic" and payload.get("has_more") else None
        )
        if protocol == "anthropic" and payload.get("has_more") and not next_cursor:
            raise CatalogResponseError("invalid_response")
        if not next_cursor:
            return sorted(models.values(), key=lambda m: m["id"].casefold()), False
        if not isinstance(next_cursor, str) or len(next_cursor) > 2000 or key in next_cursor or next_cursor in seen_cursors:
            raise CatalogResponseError("invalid_response")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return sorted(models.values(), key=lambda m: m["id"].casefold()), True


def sync_relay_models(db: Session, target: ProbeTarget, *, client=None, group_client=None) -> bool:
    active = (
        RelayStation.id == target.id, RelayStation.monitor_revision == target.monitor_revision,
        RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
    )
    if db.scalar(select(RelayStation.id).where(*active)) is None:
        return False
    checked_at = datetime.now(timezone.utc)
    models = None
    truncated = False
    key = ""
    try:
        key = decrypt_secret(target.encrypted_api_key)
        if not key or not target.base_url:
            status = "config_error"
        else:
            models, truncated = fetch_relay_models(target, key, client=client)
            status = "ok"
    except CatalogResponseError as exc:
        status = exc.status
    except TimeoutError:
        status = "timeout"
    except (OSError, HTTPException):
        status = "connection_error"
    except (ValueError, TypeError, RecursionError):
        status = "invalid_response"
    except RuntimeError:
        status = "credential_error"
    # Group metadata has its own request budget and success state;
    # a failed model list must not suppress otherwise valid group metadata.
    from .relay_groups import fetch_group_catalog
    group_catalog = fetch_group_catalog(target, key, client=group_client) if key else None
    station = db.scalar(select(RelayStation).where(*active).execution_options(populate_existing=True))
    if station is None:
        db.rollback()
        return False
    previous = station.model_catalog or {}
    if previous.get("checked_at", "") > checked_at.isoformat():
        db.rollback()
        return False
    catalog = {**previous, "status": status, "checked_at": checked_at.isoformat()}
    if models is not None:
        catalog.update(models=models, truncated=truncated, synced_at=checked_at.isoformat())
    if group_catalog is not None:
        previous_groups = previous.get("group_catalog", {})
        if group_catalog["status"] != "ok":
            group_catalog = {**previous_groups, "status": group_catalog["status"], "checked_at": group_catalog["checked_at"]}
        catalog["group_catalog"] = group_catalog
    # The final write checks both configuration and cache version. This is
    # atomic on SQLite too, where SELECT FOR UPDATE cannot protect a save.
    cache_version = RelayStation.model_catalog["checked_at"].as_string()
    expected_version = previous.get("checked_at")
    saved = db.execute(update(RelayStation).where(
        *active, cache_version == expected_version if expected_version else cache_version.is_(None),
    ).values(model_catalog=catalog).execution_options(synchronize_session=False))
    if saved.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    db.expire(station, ["model_catalog", "updated_at"])
    return True


def run_due_model_syncs(session_factory, stop_event: Event | None = None) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    checked_at = RelayStation.model_catalog["checked_at"].as_string()
    with session_factory() as db:
        targets = [ProbeTarget(**row) for row in db.execute(select(
            RelayStation.id, RelayStation.monitor_revision, RelayStation.base_url,
            RelayStation.probe_protocol, RelayStation.probe_model, RelayStation.encrypted_api_key,
        ).where(
            RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
            RelayStation.base_url != "", RelayStation.encrypted_api_key != "",
            or_(checked_at.is_(None), checked_at <= cutoff),
        ).order_by(RelayStation.id).limit(100)).mappings()]
    for target in targets:
        if stop_event is not None and stop_event.is_set():
            break
        with session_factory() as db:
            sync_relay_models(db, target)


async def relay_model_sync_loop(session_factory) -> None:
    stop_event = Event()
    try:
        while True:
            try:
                await asyncio.to_thread(run_due_model_syncs, session_factory, stop_event)
            except Exception:
                logger.error("Relay model and group sync cycle failed; will retry next cycle")
            await asyncio.sleep(60)
    finally:
        # Cancelling to_thread does not stop its worker. Prevent it from
        # starting another station after lifespan shutdown cancels this task.
        stop_event.set()
