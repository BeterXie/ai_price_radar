from __future__ import annotations

import urllib.parse

from .config import Settings


_PLACEHOLDERS = {
    "",
    "replace-with-at-least-32-random-bytes",
    "replace-with-a-separate-intake-worker-key",
    "replace-with-a-separate-detector-worker-key",
    "replace-with-a-separate-discovery-worker-key",
    "pricememo-auth-secret-key-change-in-production",
}


def _is_https_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme.casefold() == "https" and bool(parsed.hostname)


def validate_api_runtime_settings(settings: Settings) -> None:
    if settings.app_env.strip().casefold() != "production":
        return

    errors: list[str] = []
    secrets = {
        "ADMIN_API_KEY": settings.admin_api_key,
        "INTAKE_WORKER_KEY": settings.intake_worker_key,
        "DETECTOR_WORKER_KEY": settings.detector_worker_key,
        "DISCOVERY_WORKER_KEY": settings.discovery_worker_key,
        "SESSION_SECRET_KEY": settings.session_secret_key,
        "BOT_SECRET_ENCRYPTION_KEY": settings.bot_secret_encryption_key,
    }
    for name, value in secrets.items():
        if value in _PLACEHOLDERS or len(value.encode("utf-8")) < 32:
            errors.append(f"{name} must contain at least 32 non-placeholder bytes")

    worker_keys = [
        settings.admin_api_key,
        settings.intake_worker_key,
        settings.detector_worker_key,
        settings.discovery_worker_key,
    ]
    if len(set(worker_keys)) != len(worker_keys):
        errors.append("administrator and worker keys must all be distinct")
    if settings.bot_secret_encryption_key == settings.session_secret_key:
        errors.append("BOT_SECRET_ENCRYPTION_KEY must differ from SESSION_SECRET_KEY")

    if settings.qq_mock_auth_enabled:
        errors.append("QQ_MOCK_AUTH_ENABLED must be disabled")
    if settings.dev_print_auth_codes:
        errors.append("DEV_PRINT_AUTH_CODES must be disabled")
    if settings.seed_demo_data:
        errors.append("SEED_DEMO_DATA must be disabled")
    if settings.api_docs_enabled:
        errors.append("API_DOCS_ENABLED must be disabled")
    if not _is_https_url(settings.public_site_url):
        errors.append("PUBLIC_SITE_URL must be an absolute HTTPS URL")
    if not _is_https_url(settings.web_origin):
        errors.append("WEB_ORIGIN must be an absolute HTTPS URL")
    if settings.smtp_username and not (settings.smtp_starttls or settings.smtp_ssl):
        errors.append("SMTP authentication requires STARTTLS or SMTP_SSL")
    if settings.smtp_starttls and settings.smtp_ssl:
        errors.append("SMTP_STARTTLS and SMTP_SSL cannot both be enabled")

    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))
