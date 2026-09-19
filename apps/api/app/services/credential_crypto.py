from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..models import QQBindingSession, UserBotBinding

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_AAD = b"pricememo:credential:v1"


def _materials(settings: Settings) -> list[str]:
    values: list[str] = []
    for value in (settings.bot_secret_encryption_key, settings.session_secret_key):
        clean = (value or "").strip()
        if clean and clean not in values:
            values.append(clean)
    return values


def _key_from_material(material: str) -> bytes:
    if len(material.encode("utf-8")) < 32:
        raise RuntimeError("credential encryption key must contain at least 32 bytes")
    return hashlib.sha256(material.encode("utf-8")).digest()


def _key_id(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def _primary_material(settings: Settings) -> str:
    values = _materials(settings)
    if not values:
        raise RuntimeError("credential encryption key is not configured")
    material = values[0]
    _key_from_material(material)
    return material


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and value.startswith(_PREFIX))


def _encrypt_plain(value: str, settings: Settings) -> str:
    material = _primary_material(settings)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key_from_material(material)).encrypt(
        nonce, value.encode("utf-8"), _AAD
    )
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_PREFIX}{_key_id(material)}:{payload}"


def decrypt_secret(value: str | None, settings: Settings | None = None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if not is_encrypted_secret(raw):
        # Backward compatibility for rows created before encrypted-at-rest storage.
        return raw

    settings = settings or get_settings()
    encoded = raw[len(_PREFIX):]
    stored_key_id = ""
    if ":" in encoded:
        maybe_key_id, payload = encoded.split(":", 1)
        if len(maybe_key_id) == 12:
            stored_key_id = maybe_key_id
            encoded = payload

    try:
        payload_bytes = base64.urlsafe_b64decode(encoded.encode("ascii"))
        nonce, ciphertext = payload_bytes[:12], payload_bytes[12:]
    except Exception as exc:
        raise RuntimeError("stored credential has invalid encoding") from exc

    materials = _materials(settings)
    if stored_key_id:
        materials.sort(key=lambda item: _key_id(item) != stored_key_id)

    for material in materials:
        try:
            return AESGCM(_key_from_material(material)).decrypt(
                nonce, ciphertext, _AAD
            ).decode("utf-8")
        except Exception:
            continue
    raise RuntimeError("stored credential cannot be decrypted with configured keys")


def encrypt_secret(value: str | None, settings: Settings | None = None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    settings = settings or get_settings()
    primary = _primary_material(settings)
    primary_id = _key_id(primary)
    if is_encrypted_secret(raw):
        encoded = raw[len(_PREFIX):]
        if encoded.startswith(f"{primary_id}:"):
            return raw
        raw = decrypt_secret(raw, settings)
    return _encrypt_plain(raw, settings)


def migrate_bot_credentials(db: Session, settings: Settings | None = None) -> int:
    """Encrypt plaintext credentials and re-key older ciphertext to the primary key."""
    settings = settings or get_settings()
    changed = 0
    for binding in db.scalars(select(UserBotBinding).where(UserBotBinding.bot_token != "")).all():
        migrated = encrypt_secret(binding.bot_token, settings)
        if migrated != binding.bot_token:
            binding.bot_token = migrated
            changed += 1
    for pending in db.scalars(select(QQBindingSession).where(QQBindingSession.qq_key != "")).all():
        migrated = encrypt_secret(pending.qq_key, settings)
        if migrated != pending.qq_key:
            pending.qq_key = migrated
            changed += 1
    if changed:
        db.commit()
        logger.info("Encrypted or re-keyed %d stored bot credential value(s)", changed)
    return changed
