from __future__ import annotations

import logging
import smtplib
import ssl
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import resend
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..models import AdminBroadcast, NotificationOutbox, User, UserBotBinding
from .credential_crypto import decrypt_secret
from .source_intake import sanitize_header_value, sanitize_recipient_email

logger = logging.getLogger(__name__)

SEND_LEASE = timedelta(minutes=10)
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))
# The three delays are followed by one final failed attempt.
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def smtp_is_configured(settings: Settings) -> bool:
    base_ready = bool(settings.smtp_host.strip() and settings.smtp_from.strip())
    secure_auth = not settings.smtp_username.strip() or settings.smtp_starttls or settings.smtp_ssl
    return base_ready and secure_auth


def resend_is_configured(settings: Settings) -> bool:
    return bool(settings.resend_api_key.strip() and settings.resend_from.strip())


def mail_is_configured(settings: Settings) -> bool:
    return resend_is_configured(settings) or smtp_is_configured(settings)


def _sanitized_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: notification delivery failed"


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
    if not settings.smtp_host.strip() or not settings.smtp_from.strip():
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["From"] = sanitize_header_value(settings.smtp_from)
    message["To"] = sanitize_recipient_email(row.recipient)
    message["Subject"] = sanitize_header_value(row.subject)
    message.set_content(row.text_body)
    if settings.smtp_starttls and settings.smtp_ssl:
        raise RuntimeError("SMTP_STARTTLS and SMTP_SSL cannot both be enabled")
    if settings.smtp_username and not (settings.smtp_starttls or settings.smtp_ssl):
        raise RuntimeError("SMTP authentication requires STARTTLS or SMTP_SSL")
    smtp_client = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
    smtp_kwargs = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "timeout": settings.smtp_timeout_seconds,
    }
    if settings.smtp_ssl:
        smtp_kwargs["context"] = ssl.create_default_context()
    with smtp_client(**smtp_kwargs) as client:
        if settings.smtp_starttls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)



def send_notification_message(row: NotificationOutbox, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if resend_is_configured(settings):
        send_resend_message(row, settings)
        return
    send_smtp_message(row, settings)


def _broadcast_id(row: NotificationOutbox) -> int | None:
    parts = row.dedupe_key.split(":")
    if len(parts) < 2 or parts[0] != "broadcast":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _bot_binding_id(row: NotificationOutbox) -> int:
    parts = row.dedupe_key.split(":")
    if len(parts) < 5 or parts[-2] != "bot":
        raise RuntimeError("bot notification has an invalid dedupe key")
    try:
        return int(parts[-1])
    except ValueError as exc:
        raise RuntimeError("bot notification has an invalid binding id") from exc


def send_bot_message(db: Session, row: NotificationOutbox) -> None:
    binding = db.get(UserBotBinding, _bot_binding_id(row))
    if binding is None or not binding.is_active or not binding.target_id:
        raise RuntimeError("bot binding is unavailable")
    user = db.get(User, binding.user_id)
    if user is None or not user.is_active:
        raise RuntimeError("bot recipient is inactive")
    if binding.target_id != row.recipient:
        raise RuntimeError("bot notification recipient does not match binding")

    from extensions.bots.qq_bot import QQBotClient

    app_id = (binding.extra_meta or {}).get("app_id") if isinstance(binding.extra_meta, dict) else None
    app_secret = decrypt_secret(binding.bot_token) or None
    client = QQBotClient(app_id=app_id, app_secret=app_secret)
    if not client.is_configured:
        raise RuntimeError("bot binding credentials are unavailable")
    if not client.send_c2c_message(binding.target_id, row.text_body, app_id=app_id, app_secret=app_secret):
        raise RuntimeError("bot delivery failed")


def refresh_broadcast_status(db: Session, broadcast_id: int) -> None:
    broadcast = db.get(AdminBroadcast, broadcast_id)
    if broadcast is None:
        return
    statuses = list(
        db.scalars(
            select(NotificationOutbox.status).where(
                NotificationOutbox.dedupe_key.like(f"broadcast:{broadcast_id}:%")
            )
        )
    )
    if not statuses or all(status == "sent" for status in statuses):
        broadcast.status = "sent"
    elif any(status in {"pending", "sending"} for status in statuses):
        broadcast.status = "queued"
    elif any(status == "sent" for status in statuses):
        broadcast.status = "partial"
    else:
        broadcast.status = "failed"


def claim_due(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 20,
    bot_only: bool = False,
) -> list[NotificationOutbox]:
    now = now or utcnow()
    db.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.status == "sending",
            NotificationOutbox.next_attempt_at <= now,
        )
        .values(status="pending")
    )
    stmt = select(NotificationOutbox).where(
        NotificationOutbox.status == "pending",
        NotificationOutbox.next_attempt_at <= now,
    )
    if bot_only:
        stmt = stmt.where(NotificationOutbox.event_type == "admin_broadcast_bot")
    rows = list(
        db.scalars(
            stmt
            .order_by(NotificationOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for row in rows:
        row.status = "sending"
        row.next_attempt_at = now + SEND_LEASE
        row._claim_lease_expires_at = row.next_attempt_at
    db.commit()
    return rows


def _locked_claim(
    db: Session,
    row_id: int,
    lease_expires_at: datetime,
) -> NotificationOutbox | None:
    return db.scalar(
        select(NotificationOutbox)
        .where(
            NotificationOutbox.id == row_id,
            NotificationOutbox.status == "sending",
            NotificationOutbox.next_attempt_at == lease_expires_at,
        )
        .with_for_update()
    )


def mark_sent(
    db: Session,
    row_id: int,
    *,
    lease_expires_at: datetime,
    now: datetime | None = None,
) -> bool:
    now = now or utcnow()
    row = _locked_claim(db, row_id, lease_expires_at)
    if row is None:
        db.commit()
        return False
    row.status = "sent"
    row.attempt_count += 1
    row.next_attempt_at = now
    row.last_error = ""
    row.sent_at = now
    broadcast_id = _broadcast_id(row)
    if broadcast_id is not None:
        counter = (
            AdminBroadcast.bot_sent_count
            if row.event_type == "admin_broadcast_bot"
            else AdminBroadcast.email_sent_count
        )
        db.execute(
            update(AdminBroadcast)
            .where(AdminBroadcast.id == broadcast_id)
            .values({counter.key: counter + 1})
        )
        db.flush()
        refresh_broadcast_status(db, broadcast_id)
    db.commit()
    return True


def mark_failed(
    db: Session,
    row_id: int,
    exc: Exception,
    *,
    lease_expires_at: datetime,
    now: datetime | None = None,
) -> bool:
    now = now or utcnow()
    row = _locked_claim(db, row_id, lease_expires_at)
    if row is None:
        db.commit()
        return False
    row.attempt_count += 1
    row.last_error = _sanitized_error(exc)
    if row.attempt_count >= MAX_ATTEMPTS:
        row.status = "failed"
        row.next_attempt_at = now
    else:
        row.status = "pending"
        row.next_attempt_at = now + RETRY_DELAYS[row.attempt_count - 1]
    broadcast_id = _broadcast_id(row)
    if broadcast_id is not None:
        db.flush()
        refresh_broadcast_status(db, broadcast_id)
    db.commit()
    return True


def process_once(
    db: Session,
    *,
    send: Callable[[NotificationOutbox], None] | None = None,
    now: datetime | None = None,
    limit: int = 20,
) -> int:
    settings = get_settings()
    mail_ready = mail_is_configured(settings)
    if send is None and not mail_ready:
        logger.warning("Resend/SMTP 未配置，邮件通知保持待发送；仍处理可用的机器人通知")
    rows = claim_due(db, now=now, limit=limit, bot_only=send is None and not mail_ready)
    sent = 0
    for row in rows:
        lease_expires_at = row._claim_lease_expires_at
        try:
            if send is not None:
                send(row)
            elif row.event_type == "admin_broadcast_bot":
                send_bot_message(db, row)
            else:
                send_notification_message(row, settings)
        except Exception as exc:  # Delivery errors must not escape into the API transaction.
            logger.error("邮件发送失败，已按退避策略处理：%s", _sanitized_error(exc))
            mark_failed(db, row.id, exc, lease_expires_at=lease_expires_at, now=now)
        else:
            if mark_sent(db, row.id, lease_expires_at=lease_expires_at, now=now):
                sent += 1
    return sent
