from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import psycopg


DDL = """
CREATE TABLE IF NOT EXISTS source_intakes (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT UNIQUE REFERENCES reports(id) ON DELETE SET NULL,
    source_type VARCHAR(30) NOT NULL,
    source_key VARCHAR(300) NOT NULL,
    source_url TEXT NOT NULL,
    shop_name TEXT NOT NULL DEFAULT '',
    contact_email VARCHAR(200) NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    origin VARCHAR(30) NOT NULL DEFAULT 'manual',
    status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    decision_note TEXT NOT NULL DEFAULT '',
    failure_reason TEXT NOT NULL DEFAULT '',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    product_count INTEGER NOT NULL DEFAULT 0,
    lease_expires_at TIMESTAMPTZ NULL,
    approved_at TIMESTAMPTZ NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_source_intakes_source ON source_intakes (source_type, source_key);
CREATE INDEX IF NOT EXISTS ix_source_intakes_status ON source_intakes (status);
CREATE INDEX IF NOT EXISTS ix_source_intakes_status_lease ON source_intakes (status, lease_expires_at);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    recipient VARCHAR(200) NOT NULL,
    subject VARCHAR(300) NOT NULL,
    text_body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT NOT NULL DEFAULT '',
    dedupe_key VARCHAR(300) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_notification_outbox_due ON notification_outbox (status, next_attempt_at);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_source_intakes_type') THEN
        ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
            CHECK (source_type IN ('ldxp', 'merchant_feed'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_source_intakes_status') THEN
        ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status
            CHECK (status IN ('pending_review', 'queued', 'validating', 'validated', 'onboarded', 'rejected', 'no_products', 'validation_failed'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_notification_outbox_status') THEN
        ALTER TABLE notification_outbox ADD CONSTRAINT ck_notification_outbox_status
            CHECK (status IN ('pending', 'sending', 'sent', 'failed'));
    END IF;
END $$;
"""

LDXP_SHOP_PATH = re.compile(r"/shop/([A-Za-z0-9._~-]+)", re.IGNORECASE)


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _label(message: str, name: str) -> str:
    prefix = f"{name}："
    for line in message.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def normalize_historical_source(source_type: str, source_url: str, report_id: int) -> tuple[str, str]:
    source_type = source_type if source_type in {"ldxp", "merchant_feed"} else "ldxp"
    parsed = urlsplit(source_url)
    if source_type == "ldxp":
        match = LDXP_SHOP_PATH.fullmatch(parsed.path.rstrip("/"))
        if match:
            token = unquote(match.group(1)).strip()
            if re.fullmatch(r"[A-Za-z0-9._~-]+", token):
                return token.casefold(), f"https://pay.ldxp.cn/shop/{quote(token, safe='._~-')}"
    if parsed.scheme and parsed.netloc:
        normalized = urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path or "/", parsed.query, ""))
        return normalized, normalized
    return f"legacy-report-{report_id}", source_url.strip()


def historical_intake_status(report_status: str, known_source: bool) -> str:
    if known_source:
        return "onboarded"
    if report_status == "rejected":
        return "rejected"
    return "pending_review"


def migrate_history(connection: psycopg.Connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT token, source_url FROM shops")
        known = {str(value).casefold() for row in cursor.fetchall() for value in row if value}
        cursor.execute(
            "SELECT id, status, message, contact, created_at FROM reports "
            "WHERE kind = 'shop_request' ORDER BY id"
        )
        rows = cursor.fetchall()
        migrated = 0
        for report_id, report_status, message, contact, created_at in rows:
            message = str(message or "")
            source_type = _label(message, "来源类型") or "ldxp"
            source_url = _label(message, "店铺链接")
            source_key, normalized_url = normalize_historical_source(source_type, source_url, report_id)
            source_type = source_type if source_type in {"ldxp", "merchant_feed"} else "ldxp"
            known_source = source_key.casefold() in known or normalized_url.casefold() in known
            status = historical_intake_status(str(report_status or ""), known_source)
            now = datetime.now(timezone.utc)
            finished_at = now if status in {"onboarded", "rejected"} else None
            decision_note = "历史 Report 已存在正式 Shop" if status == "onboarded" else "历史 Report 已驳回" if status == "rejected" else "历史申请重新进入初审"
            cursor.execute(
                """
                INSERT INTO source_intakes(
                    report_id, source_type, source_key, source_url, shop_name, contact_email,
                    note, origin, status, decision_note, approved_at, finished_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual', %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    report_id,
                    source_type,
                    source_key,
                    normalized_url,
                    _label(message, "店铺名称"),
                    str(contact or ""),
                    _label(message, "申请说明"),
                    status,
                    decision_note,
                    created_at if status == "onboarded" else None,
                    finished_at,
                    created_at,
                    now,
                ),
            )
            migrated += cursor.rowcount
        return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="Add source-intake state machine and notification outbox")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
        migrated = migrate_history(connection)
        connection.commit()
    print(f"shop intake v6 migration complete; historical rows migrated: {migrated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
