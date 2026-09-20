import ssl
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database import Base
from app.models import NotificationOutbox
from app.services.outbox import SEND_LEASE, claim_due, mark_failed, mark_sent, send_smtp_message


def test_smtp_starttls_verifies_server_certificate(monkeypatch):
    contexts = []

    class SMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def starttls(self, *, context):
            contexts.append(context)

        def send_message(self, _message):
            pass

    monkeypatch.setattr("app.services.outbox.smtplib.SMTP", SMTP)
    settings = Settings(_env_file=None, smtp_host="smtp.example.com", smtp_from="sender@example.com")
    row = NotificationOutbox(recipient="recipient@example.com", subject="Test", text_body="Test")
    send_smtp_message(row, settings)
    assert len(contexts) == 1
    assert contexts[0].check_hostname is True
    assert contexts[0].verify_mode == ssl.CERT_REQUIRED


def test_smtp_auth_rejects_plaintext_connection():
    settings = Settings(
        _env_file=None,
        smtp_host="smtp.example.com",
        smtp_from="sender@example.com",
        smtp_username="sender",
        smtp_password="secret",
        smtp_starttls=False,
        smtp_ssl=False,
    )
    row = NotificationOutbox(recipient="recipient@example.com", subject="Test", text_body="Test")
    with pytest.raises(RuntimeError, match="requires STARTTLS or SMTP_SSL"):
        send_smtp_message(row, settings)


def test_stale_outbox_worker_cannot_overwrite_a_new_lease():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    claimed_at = datetime(2026, 9, 20, 1, 0, tzinfo=timezone.utc)
    with Session(engine) as db:
        db.add(
            NotificationOutbox(
                event_type="test",
                recipient="recipient@example.com",
                subject="Test",
                text_body="Test",
                dedupe_key="test:stale-lease",
                next_attempt_at=claimed_at,
            )
        )
        db.commit()

    with Session(engine) as first_worker:
        first = claim_due(first_worker, now=claimed_at)
        row_id = first[0].id
        first_lease = first[0]._claim_lease_expires_at

    reclaimed_at = claimed_at + SEND_LEASE
    with Session(engine) as second_worker:
        second = claim_due(second_worker, now=reclaimed_at)
        second_lease = second[0]._claim_lease_expires_at

        with Session(engine) as stale_worker:
            assert mark_failed(
                stale_worker,
                row_id,
                RuntimeError("late failure"),
                lease_expires_at=first_lease,
                now=reclaimed_at,
            ) is False

        assert mark_sent(
            second_worker,
            row_id,
            lease_expires_at=second_lease,
            now=reclaimed_at,
        ) is True

    with Session(engine) as db:
        row = db.get(NotificationOutbox, row_id)
        assert row.status == "sent"
        assert row.attempt_count == 1
        assert row.last_error == ""
