from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..models import QQBindingSession, ReportRateLimit, User, UserActionLog, UserSession


def cleanup_privacy_data(db: Session, settings: Settings | None = None) -> dict[str, int]:
    """Bound retention of raw IP/User-Agent records and expired transient auth data."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.privacy_log_retention_days)
    limiter_cutoff = now - timedelta(days=2)

    action_logs = db.execute(
        delete(UserActionLog).where(UserActionLog.created_at < cutoff)
    ).rowcount or 0
    expired_sessions = db.execute(
        delete(UserSession).where(UserSession.expires_at < now)
    ).rowcount or 0
    expired_bindings = db.execute(
        delete(QQBindingSession).where(QQBindingSession.expires_at < now)
    ).rowcount or 0
    old_limiters = db.execute(
        delete(ReportRateLimit).where(ReportRateLimit.window_started_at < limiter_cutoff)
    ).rowcount or 0
    anonymized_users = db.execute(
        update(User)
        .where(User.last_login_at.is_not(None), User.last_login_at < cutoff, User.last_login_ip != "")
        .values(last_login_ip="")
    ).rowcount or 0

    db.commit()
    return {
        "action_logs": int(action_logs),
        "expired_sessions": int(expired_sessions),
        "expired_bindings": int(expired_bindings),
        "rate_limits": int(old_limiters),
        "anonymized_users": int(anonymized_users),
    }
