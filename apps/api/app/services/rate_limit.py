from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ReportRateLimit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def consume_rate_limit(
    db: Session,
    namespace: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
) -> bool:
    """Consume one request from a DB-backed fixed window.

    The key is hashed so raw IP addresses / account identifiers are not stored
    in the limiter table. Callers decide when to commit; flush keeps the row
    visible to the current transaction.
    """
    if limit < 1 or window_seconds < 1:
        raise ValueError("rate limit and window_seconds must be positive")

    identity = (identity or "unknown").strip()
    client_key = hashlib.sha256(
        f"{namespace}:{identity}".encode("utf-8")
    ).hexdigest()
    now = _utcnow()

    rate = db.scalar(
        select(ReportRateLimit)
        .where(ReportRateLimit.client_key == client_key)
        .with_for_update()
    )
    if rate is None:
        db.add(
            ReportRateLimit(
                client_key=client_key,
                window_started_at=now,
                request_count=1,
                updated_at=now,
            )
        )
        db.flush()
        return True

    started_at = _ensure_utc(rate.window_started_at)
    if now - started_at >= timedelta(seconds=window_seconds):
        rate.window_started_at = now
        rate.request_count = 1
        rate.updated_at = now
        db.flush()
        return True

    if rate.request_count >= limit:
        return False

    rate.request_count += 1
    rate.updated_at = now
    db.flush()
    return True
