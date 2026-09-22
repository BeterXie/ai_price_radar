from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, update
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..models import (
    AuthCode,
    NotificationOutbox,
    OfferClick,
    QQBindingSession,
    ReportRateLimit,
    ShopCoupon,
    User,
    UserActionLog,
    UserSession,
)


def cleanup_privacy_data(db: Session, settings: Settings | None = None) -> dict[str, int]:
    """Bound retention of raw IP/User-Agent records and expired transient auth data."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.privacy_log_retention_days)
    limiter_cutoff = now - timedelta(days=2)
    auth_artifact_cutoff = now - timedelta(days=1)

    action_logs = db.execute(
        delete(UserActionLog).where(UserActionLog.created_at < cutoff)
    ).rowcount or 0
    expired_sessions = db.execute(
        delete(UserSession).where(UserSession.expires_at < now)
    ).rowcount or 0
    anonymized_sessions = db.execute(
        update(UserSession)
        .where(
            UserSession.created_at < cutoff,
            or_(UserSession.ip_address != "", UserSession.user_agent != ""),
        )
        .values(ip_address="", user_agent="")
    ).rowcount or 0
    expired_bindings = db.execute(
        delete(QQBindingSession).where(QQBindingSession.expires_at < now)
    ).rowcount or 0
    old_limiters = db.execute(
        delete(ReportRateLimit).where(ReportRateLimit.window_started_at < limiter_cutoff)
    ).rowcount or 0
    expired_auth_codes = db.execute(
        delete(AuthCode).where(AuthCode.expires_at < now)
    ).rowcount or 0
    old_notifications = db.execute(
        delete(NotificationOutbox).where(
            or_(
                NotificationOutbox.created_at < cutoff,
                and_(
                    NotificationOutbox.event_type == "auth_login_code",
                    NotificationOutbox.created_at < auth_artifact_cutoff,
                ),
            )
        )
    ).rowcount or 0
    old_offer_clicks = db.execute(
        delete(OfferClick).where(OfferClick.created_at < cutoff)
    ).rowcount or 0
    expired_unassigned_coupons = db.execute(
        delete(ShopCoupon)
        .where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.expires_at < now,
        )
        .execution_options(synchronize_session="fetch")
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
        "anonymized_sessions": int(anonymized_sessions),
        "expired_bindings": int(expired_bindings),
        "rate_limits": int(old_limiters),
        "expired_auth_codes": int(expired_auth_codes),
        "notification_outbox": int(old_notifications),
        "offer_clicks": int(old_offer_clicks),
        "expired_unassigned_coupons": int(expired_unassigned_coupons),
        "anonymized_users": int(anonymized_users),
    }
