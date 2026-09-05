from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.email import normalize_email
from ..models import NotificationOutbox, SourceIntake

logger = logging.getLogger(__name__)

PENDING_INTAKE_STATUSES = {"pending_review", "queued", "validating", "validated", "no_products", "validation_failed"}
TERMINAL_INTAKE_STATUSES = {"onboarded", "rejected"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def admin_recipients() -> list[str]:
    values = get_settings().shop_intake_admin_emails.replace(";", ",").split(",")
    result: list[str] = []
    for value in values:
        recipient = value.strip()
        if recipient and recipient not in result:
            result.append(recipient)
    return result


def site_url(path: str) -> str:
    return f"{get_settings().public_site_url.rstrip('/')}/{path.lstrip('/')}"


def _insert_outbox_row(db: Session, values: dict[str, object]) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        db.execute(
            insert(NotificationOutbox)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
        )
        db.flush()
        return
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        db.execute(
            insert(NotificationOutbox)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
        )
        db.flush()
        return
    existing = db.scalar(
        select(NotificationOutbox.id).where(NotificationOutbox.dedupe_key == values["dedupe_key"])
    )
    if existing is not None:
        return
    db.add(NotificationOutbox(**values))
    db.flush()


def sanitize_header_value(value: str, max_length: int = 200) -> str:
    """Strip CRLF and control characters to prevent email header injection."""
    cleaned = re.sub(r"[\r\n\t\x00-\x1f\x7f]+", " ", str(value or "")).strip()
    return re.sub(r" +", " ", cleaned)[:max_length]


def sanitize_recipient_email(value: str) -> str:
    """Validate and sanitize recipient email to prevent header injection or open relay."""
    return normalize_email(value)


def enqueue_outbox(
    db: Session,
    *,
    event_type: str,
    recipient: str,
    subject: str,
    text_body: str,
    dedupe_key: str,
) -> None:
    safe_recipient = sanitize_recipient_email(recipient)
    safe_subject = sanitize_header_value(subject)
    if not dedupe_key or len(dedupe_key) > 300 or re.search(r"[\x00-\x1f\x7f]", dedupe_key):
        raise ValueError("notification dedupe key must be non-empty and at most 300 characters")
    _insert_outbox_row(
        db,
        {
            "event_type": event_type,
            "recipient": safe_recipient,
            "subject": safe_subject,
            "text_body": text_body,
            "status": "pending",
            "attempt_count": 0,
            "next_attempt_at": utcnow(),
            "last_error": "",
            "dedupe_key": dedupe_key,
        },
    )


def enqueue_submission_notifications(db: Session, intake: SourceIntake) -> None:
    for recipient in admin_recipients():
        enqueue_outbox(
            db,
            event_type="shop_request.submitted.admin",
            recipient=recipient,
            subject="新的店铺收录申请",
            text_body=(
                f"收到新的店铺收录申请（#{intake.id}）。\n"
                f"来源类型：{intake.source_type}\n"
                f"来源地址：{intake.source_url}\n"
                f"来源名称：{intake.shop_name or '未填写'}\n"
                f"联系邮箱：{intake.contact_email}\n"
                f"申请说明：{intake.note or '未填写'}\n"
                f"审批地址：{site_url(f'/admin?intake={intake.id}#source-intake-{intake.id}')}\n"
                "打开后输入管理密钥，即可定位到此申请。"
            ),
            dedupe_key=f"source-intake:{intake.id}:shop_request.submitted.admin:{recipient}",
        )
    mail = get_settings()
    resend_ready = bool(mail.resend_api_key.strip() and mail.resend_from.strip())
    smtp_ready = bool(mail.smtp_host.strip() and mail.smtp_from.strip())
    if not resend_ready and not smtp_ready:
        logger.warning("Resend/SMTP 未完整配置，收录申请邮件将保留在 notification_outbox")
    enqueue_outbox(
        db,
        event_type="shop_request.submitted.applicant",
        recipient=intake.contact_email,
        subject="店铺收录申请已提交",
        text_body=(
            f"你的店铺收录申请（#{intake.id}）已提交。\n"
            f"店铺名称：{intake.shop_name or '未填写'}\n"
            f"店铺地址：{intake.source_url}\n"
            "当前状态：等待管理员初审。状态变化会通过邮件通知。"
        ),
        dedupe_key=f"source-intake:{intake.id}:shop_request.submitted.applicant",
    )


def enqueue_transition_notification(
    db: Session,
    intake: SourceIntake,
    *,
    event_type: str,
    subject: str,
    text_body: str,
    attempt: int | None = None,
) -> None:
    # Discovery-created intakes have no applicant address; admin notifications
    # still provide the audit trail, while an empty recipient cannot be queued.
    if not str(intake.contact_email or "").strip():
        return
    suffix = f":attempt-{attempt}" if attempt is not None else ""
    enqueue_outbox(
        db,
        event_type=event_type,
        recipient=intake.contact_email,
        subject=subject,
        text_body=text_body,
        dedupe_key=f"source-intake:{intake.id}:{event_type}{suffix}",
    )


def enqueue_admin_notification(
    db: Session,
    intake: SourceIntake,
    *,
    event_type: str,
    subject: str,
    text_body: str,
) -> None:
    for recipient in admin_recipients():
        enqueue_outbox(
            db,
            event_type=event_type,
            recipient=recipient,
            subject=subject,
            text_body=text_body,
            dedupe_key=f"source-intake:{intake.id}:{event_type}:{recipient}",
        )



def email_statuses(db: Session, intake_id: int) -> dict[str, str]:
    rows = list(
        db.scalars(
            select(NotificationOutbox).where(
                NotificationOutbox.dedupe_key.like(f"source-intake:{intake_id}:%")
            )
        )
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row.event_type].append(row.status)

    result: dict[str, str] = {}
    for event_type, statuses in grouped.items():
        if all(value == "sent" for value in statuses):
            result[event_type] = "sent"
        elif any(value == "failed" for value in statuses):
            result[event_type] = "failed"
        elif any(value == "sending" for value in statuses):
            result[event_type] = "sending"
        else:
            result[event_type] = "pending"
    return result
