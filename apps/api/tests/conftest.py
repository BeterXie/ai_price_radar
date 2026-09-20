import pytest

from app.core.config import get_settings
from app.services.catalog import clear_price_trend_cache

_TEST_BOT_ENCRYPTION_KEY = "test-bot-encryption-key-32-bytes-min"


@pytest.fixture(autouse=True)
def _isolated_price_trend_cache():
    """Keep the process-wide trend cache from leaking between tests.

    Fresh per-test databases restart primary keys, so a cached trend from an
    earlier test would be served here for the same (product, snapshot) key.
    """
    clear_price_trend_cache()
    yield
    clear_price_trend_cache()


@pytest.fixture(autouse=True)
def bot_encryption_key(monkeypatch):
    """Give every test a real 32+ byte bot credential key.

    credential_crypto refuses to encrypt with the public default session
    secret (fail-closed), and production preflight requires an independent
    BOT_SECRET_ENCRYPTION_KEY — tests must exercise the same contract.
    Set both the env var and the cached singleton attribute: some tests call
    get_settings.cache_clear(), which would otherwise drop the attribute.
    """
    monkeypatch.setenv("BOT_SECRET_ENCRYPTION_KEY", _TEST_BOT_ENCRYPTION_KEY)
    monkeypatch.setattr(get_settings(), "bot_secret_encryption_key", _TEST_BOT_ENCRYPTION_KEY)
    yield
    get_settings.cache_clear()
