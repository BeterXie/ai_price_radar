from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from urllib.parse import quote

from sqlalchemy import delete, inspect, or_, select, update
from sqlalchemy.orm import Session

from ..models import RelayProbeResult, RelayStation
from ..schemas import RelayHealthOut, RelayProbeSampleOut, RelayStationOut
from .credential_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)
PROBE_INTERVAL = timedelta(hours=1)
DIAGNOSTIC_STATUSES = {"credential_error", "config_error"}


@dataclass(frozen=True)
class ProbeTarget:
    id: int
    monitor_revision: int
    base_url: str
    probe_protocol: str
    probe_model: str
    encrypted_api_key: str = field(repr=False)


def configure_relay(db: Session, station: RelayStation, values: dict, api_key=None) -> None:
    changed = any(
        name in values and values[name] != getattr(station, name)
        for name in ("base_url", "probe_protocol", "probe_model")
    )
    if api_key is not None:
        raw = api_key.get_secret_value()
        # Explicit key submission always replaces a configuration. Comparing
        # against a stale ORM value could otherwise overwrite a concurrent
        # key change without advancing its revision; unreadable keys also recover.
        changed = True
        station.encrypted_api_key = encrypt_secret(raw)
    for name, value in values.items():
        setattr(station, name, value)
    if station.monitor_enabled and not (station.base_url and station.has_api_key and station.probe_model):
        raise ValueError("开启监测需要 Base URL、检测密钥和模型 ID")
    if station.review_status is None:
        station.review_status = "approved"
    if station.review_status != "approved":
        station.is_enabled = False
    if station.review_status == "rejected":
        station.monitor_enabled = False
    if changed:
        if inspect(station).persistent:
            # Increment in the UPDATE itself: concurrent editors can have
            # stale objects, but every committed configuration gets a new ID.
            station.monitor_revision = RelayStation.monitor_revision + 1
        else:
            station.monitor_revision = (station.monitor_revision or 1) + 1
        station.next_probe_at = None
        if inspect(station).persistent:
            db.flush()
            db.refresh(station, attribute_names=["monitor_revision"])


def relay_health(db: Session, station: RelayStation) -> RelayHealthOut:
    now = datetime.now(timezone.utc)
    rows = list(db.scalars(select(RelayProbeResult).where(
        RelayProbeResult.station_id == station.id,
        RelayProbeResult.revision == station.monitor_revision,
        RelayProbeResult.checked_at >= now - timedelta(hours=24),
    ).order_by(RelayProbeResult.checked_at.desc(), RelayProbeResult.id.desc())))
    valid = [row for row in rows if row.status not in DIAGNOSTIC_STATUSES]
    successes = [row for row in valid if row.status == "healthy"]
    latest = rows[0] if rows else db.scalar(select(RelayProbeResult).where(
        RelayProbeResult.station_id == station.id,
        RelayProbeResult.revision == station.monitor_revision,
    ).order_by(RelayProbeResult.checked_at.desc(), RelayProbeResult.id.desc()).limit(1))
    checked = latest.checked_at if latest else None
    if checked and checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    status = latest.status if latest else "not_checked"
    if checked and checked < now - PROBE_INTERVAL * 2:
        status = "stale"
    if not station.monitor_enabled:
        status = "disabled"
    latencies = sorted(row.latency_ms for row in successes)
    return RelayHealthOut(
        status=status,
        checked_at=checked,
        probe_model=station.probe_model,
        latency_ms=latest.latency_ms if latest else None,
        success_rate_24h=round(len(successes) / len(valid) * 100, 2) if valid else None,
        sample_count_24h=len(valid),
        diagnostic_count_24h=len(rows) - len(valid),
        p95_latency_ms=latencies[math.ceil(len(latencies) * .95) - 1] if latencies else None,
        recent_samples=[RelayProbeSampleOut(
            checked_at=row.checked_at if row.checked_at.tzinfo else row.checked_at.replace(tzinfo=timezone.utc),
            status=row.status,
            latency_ms=row.latency_ms,
        ) for row in reversed(rows[:24])],
    )


def relay_admin_out(db: Session, station: RelayStation) -> RelayStationOut:
    return RelayStationOut.model_validate(station).model_copy(update={"health": relay_health(db, station)})


def _probe_request(station: RelayStation | ProbeTarget, key: str) -> tuple[str, dict, dict]:
    base = station.base_url.rstrip("/")
    model = station.probe_model
    if station.probe_protocol == "anthropic":
        base = base if base.endswith("/v1") else base + "/v1"
        return base + "/messages", {
            "model": model, "max_tokens": 8, "messages": [{"role": "user", "content": "Reply OK"}],
        }, {"x-api-key": key, "anthropic-version": "2023-06-01"}
    if station.probe_protocol == "gemini":
        base = base if base.endswith(("/v1beta", "/v1")) else base + "/v1beta"
        model = model.removeprefix("models/")
        return base + "/models/" + quote(model, safe="") + ":generateContent", {
            "contents": [{"parts": [{"text": "Reply OK"}]}], "generationConfig": {"maxOutputTokens": 8},
        }, {"x-goog-api-key": key}
    base = base if base.endswith("/v1") else base + "/v1"
    return base + "/chat/completions", {
        "model": model, "max_tokens": 8, "stream": False,
        "messages": [{"role": "user", "content": "Reply OK"}],
    }, {"Authorization": "Bearer " + key}


def _has_text(content: object) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    return isinstance(content, list) and any(
        isinstance(part, dict) and isinstance(part.get("text"), str) and bool(part["text"].strip())
        for part in content
    )


def _has_completion(protocol: str, payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("error"):
        return False
    if protocol == "anthropic":
        content = payload.get("content")
        return isinstance(content, list) and _has_text(content)
    if protocol == "gemini":
        candidates = payload.get("candidates")
        return isinstance(candidates, list) and any(
            isinstance(row, dict) and isinstance(row.get("content"), dict)
            and isinstance(row["content"].get("parts"), list) and _has_text(row["content"]["parts"])
            for row in candidates
        )
    choices = payload.get("choices")
    return isinstance(choices, list) and any(
        isinstance(row, dict) and isinstance(row.get("message"), dict) and _has_text(row["message"].get("content"))
        for row in choices
    )


def probe_relay(db: Session, station: RelayStation | ProbeTarget, *, client=None) -> RelayProbeResult | None:
    """One bounded completion; neither responses nor exceptions containing secrets are saved."""
    from price_radar_http import PinnedHTTPSClient

    if isinstance(station, ProbeTarget) and db.scalar(select(RelayStation.id).where(
        RelayStation.id == station.id, RelayStation.monitor_revision == station.monitor_revision,
        RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
        RelayStation.monitor_enabled.is_(True),
    )) is None:
        return None  # Configuration changes invalidate claims that have not started.
    started = time.monotonic()
    checked_at = datetime.now(timezone.utc)
    http_status = None
    try:
        key = decrypt_secret(station.encrypted_api_key)
        if not (key and station.base_url and station.probe_model):
            status = "config_error"
        else:
            url, payload, headers = _probe_request(station, key)
            client = client or PinnedHTTPSClient(
                max_response_bytes=64 * 1024, max_task_bytes=64 * 1024,
                max_task_seconds=20, request_timeout=15,
            )
            response = client.post_json(url, payload, headers=headers)
            http_status = response.status_code
            if http_status in (401, 403):
                status = "credential_error"
            elif http_status in (400, 404, 405, 422):
                status = "config_error"
            elif http_status == 429:
                status = "rate_limited"
            elif 200 <= http_status < 300:
                try:
                    status = "healthy" if _has_completion(station.probe_protocol, json.loads(response.body)) else "invalid_response"
                except (ValueError, TypeError):
                    status = "invalid_response"
            else:
                status = "unhealthy"
    except TimeoutError:
        status = "timeout"
    except (OSError, ValueError, HTTPException):
        status = "connection_error"
    except RuntimeError:
        status = "credential_error"
    result = RelayProbeResult(
        station_id=station.id, revision=station.monitor_revision,
        checked_at=checked_at, status=status, http_status=http_status,
        latency_ms=max(0, round((time.monotonic() - started) * 1000)),
    )
    db.add(result)
    db.commit()
    return result


def claim_probe(db: Session, station_id: int) -> ProbeTarget | None:
    now = datetime.now(timezone.utc)
    claimed = db.execute(update(RelayStation).where(
        RelayStation.id == station_id,
        RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
        RelayStation.monitor_enabled.is_(True),
        or_(RelayStation.next_probe_at.is_(None), RelayStation.next_probe_at <= now),
    ).values(next_probe_at=now + PROBE_INTERVAL).returning(
        RelayStation.id, RelayStation.monitor_revision, RelayStation.base_url,
        RelayStation.probe_protocol, RelayStation.probe_model, RelayStation.encrypted_api_key,
    ).execution_options(synchronize_session=False)).mappings().one_or_none()
    target = ProbeTarget(**claimed) if claimed else None
    db.commit()
    return target


def run_due_probes(session_factory) -> None:
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        ids = list(db.scalars(select(RelayStation.id).where(
            RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
            RelayStation.monitor_enabled.is_(True),
            or_(RelayStation.next_probe_at.is_(None), RelayStation.next_probe_at <= now),
        ).order_by(RelayStation.id).limit(100)))
    for station_id in ids:
        with session_factory() as db:
            target = claim_probe(db, station_id)
            if target is not None:
                probe_relay(db, target)
    with session_factory() as db:
        db.execute(delete(RelayProbeResult).where(RelayProbeResult.checked_at < now - timedelta(days=30)))
        db.commit()


async def relay_monitor_loop(session_factory) -> None:
    while True:
        try:
            await asyncio.to_thread(run_due_probes, session_factory)
        except Exception:
            # Never log upstream exceptions: credentials may appear in their message.
            logger.error("Relay monitor cycle failed; will retry next cycle")
        await asyncio.sleep(60)
