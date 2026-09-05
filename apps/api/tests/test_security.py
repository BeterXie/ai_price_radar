import pytest
from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.security import (
    require_admin,
    require_detector_worker,
    require_discovery_worker,
    require_intake_worker,
)


def test_admin_key_has_no_usable_default(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    assert Settings(_env_file=None).admin_api_key == ""


@pytest.mark.parametrize("field,guard", [
    ("admin_api_key", require_admin),
    ("intake_worker_key", require_intake_worker),
    ("detector_worker_key", require_detector_worker),
    ("discovery_worker_key", require_discovery_worker),
])
def test_authentication_rejects_unconfigured_and_placeholder_keys(monkeypatch, field, guard):
    settings = get_settings()
    for key in ("", "   ", "replace-with-a-long-random-string"):
        monkeypatch.setattr(settings, field, key)
        with pytest.raises(HTTPException):
            guard(key)
    monkeypatch.setattr(settings, field, "configured-test-key")
    guard("configured-test-key")
    with pytest.raises(HTTPException) as error:
        guard("wrong-key")
    assert error.value.status_code == 401
