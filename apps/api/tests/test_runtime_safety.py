import pytest

from app.core.config import Settings
from app.core.runtime_safety import validate_api_runtime_settings


def _production_settings(**updates) -> Settings:
    values = {
        "app_env": "production",
        "admin_api_key": "a" * 40,
        "intake_worker_key": "b" * 40,
        "detector_worker_key": "c" * 40,
        "discovery_worker_key": "d" * 40,
        "session_secret_key": "e" * 40,
        "bot_secret_encryption_key": "f" * 40,
        "public_site_url": "https://ai.example.com",
        "web_origin": "https://ai.example.com",
        "api_docs_enabled": False,
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


def test_production_runtime_settings_accept_secure_configuration():
    validate_api_runtime_settings(_production_settings())


@pytest.mark.parametrize(
    "updates",
    [
        {"session_secret_key": "pricememo-auth-secret-key-change-in-production"},
        {"qq_mock_auth_enabled": True},
        {"dev_print_auth_codes": True},
        {"api_docs_enabled": True},
        {"web_origin": "http://ai.example.com"},
        {"smtp_username": "mailer", "smtp_starttls": False, "smtp_ssl": False},
    ],
)
def test_production_runtime_settings_fail_closed(updates):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_api_runtime_settings(_production_settings(**updates))


def test_development_runtime_does_not_require_production_secrets():
    validate_api_runtime_settings(Settings(_env_file=None, app_env="development"))
