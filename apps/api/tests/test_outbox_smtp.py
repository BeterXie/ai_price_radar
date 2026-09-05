import ssl

from app.core.config import Settings
from app.models import NotificationOutbox
from app.services.outbox import send_smtp_message


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
