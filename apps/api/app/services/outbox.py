from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import resend
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..models import NotificationOutbox
from .source_intake import sanitize_header_value, sanitize_recipient_email

logger = logging.getLogger(__name__)

SEND_LEASE = timedelta(minutes=10)
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))
# The three delays are followed by one final failed attempt.
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def smtp_is_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host.strip() and settings.smtp_from.strip())


def resend_is_configured(settings: Settings) -> bool:
    return bool(settings.resend_api_key.strip() and settings.resend_from.strip())


def mail_is_configured(settings: Settings) -> bool:
    return resend_is_configured(settings) or smtp_is_configured(settings)


def _sanitized_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: mail delivery failed"


def send_resend_message(row: NotificationOutbox, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not resend_is_configured(settings):
        raise RuntimeError("Resend is not configured")
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": sanitize_header_value(settings.resend_from),
        "to": sanitize_recipient_email(row.recipient),
        "subject": sanitize_header_value(row.subject),
        "text": row.text_body,
    })


def send_smtp_message(row: NotificationOutbox, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not smtp_is_configured(settings):
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["From"] = sanitize_header_value(settings.smtp_from)
    message["To"] = sanitize_recipient_email(row.recipient)
    message["Subject"] = sanitize_header_value(row.subject)
    message.set_content(row.text_body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as client:
        if settings.smtp_starttls:
            client.starttls()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)



def send_notification_message(row: NotificationOutbox, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if resend_is_configured(settings):
        send_resend_message(row, settings)
        return
    send_smtp_message(row, settings)


def claim_due(db: Session, *, now: datetime | None = None, limit: int = 20) -> list[NotificationOutbox]:
    now = now or utcnow()
    db.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.status == "sending",
            NotificationOutbox.next_attempt_at <= now,
        )
        .values(status="pending")
    )
    rows = list(
        db.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == "pending",
                NotificationOutbox.next_attempt_at <= now,
            )
            .order_by(NotificationOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for row in rows:
        row.status = "sending"
        row.next_attempt_at = now + SEND_LEASE
    db.commit()
    return rows


def mark_sent(db: Session, row_id: int, *, now: datetime | None = None) -> None:
    now = now or utcnow()
    row = db.get(NotificationOutbox, row_id)
    if row is None or row.status == "sent":
        return
    row.status = "sent"
    row.attempt_count += 1
    row.next_attempt_at = now
    row.last_error = ""
    row.sent_at = now
    db.commit()


def mark_failed(db: Session, row_id: int, exc: Exception, *, now: datetime | None = None) -> None:
    now = now or utcnow()
    row = db.get(NotificationOutbox, row_id)
    if row is None or row.status == "sent":
        return
    row.attempt_count += 1
    row.last_error = _sanitized_error(exc)
    if row.attempt_count >= MAX_ATTEMPTS:
        row.status = "failed"
        row.next_attempt_at = now
    else:
        row.status = "pending"
        row.next_attempt_at = now + RETRY_DELAYS[row.attempt_count - 1]
    db.commit()


def process_once(
    db: Session,
    *,
    send: Callable[[NotificationOutbox], None] | None = None,
    now: datetime | None = None,
    limit: int = 20,
) -> int:
    settings = get_settings()
    if not mail_is_configured(settings):
        logger.warning("Resend/SMTP 未配置，notification_outbox 保持待发送")
        return 0
    sender = send or send_notification_message
    rows = claim_due(db, now=now, limit=limit)
    sent = 0
    for row in rows:
        try:
            sender(row)
        except Exception as exc:  # Delivery errors must not escape into the API transaction.
            logger.error("邮件发送失败，已按退避策略处理：%s", _sanitized_error(exc))
            mark_failed(db, row.id, exc, now=now)
        else:
            mark_sent(db, row.id, now=now)
            sent += 1
    return sent
