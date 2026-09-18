from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from ..core.config import Settings, get_settings


_PREFIX = "enc:v1:"


def _fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    secret = settings.session_secret_key.encode("utf-8")
    derived = hmac.new(
        secret,
        b"price-radar:bot-credential:v1",
        hashlib.sha256,
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_bot_token(value: str, settings: Settings | None = None) -> str:
    clean = (value or "").strip()
    if not clean or clean.startswith(_PREFIX):
        return clean
    encrypted = _fernet(settings).encrypt(clean.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{encrypted}"


def decrypt_bot_token(value: str, settings: Settings | None = None) -> str:
    clean = (value or "").strip()
    if not clean:
        return ""
    if not clean.startswith(_PREFIX):
        # Backward compatibility for credentials written before encryption was
        # introduced. They are re-encrypted the next time the binding rotates.
        return clean
    try:
        return _fernet(settings).decrypt(
            clean[len(_PREFIX):].encode("ascii")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored bot credential") from exc
