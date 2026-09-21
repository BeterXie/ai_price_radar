"""Password hashing and verification for email + password login.

Uses stdlib PBKDF2-HMAC-SHA256 (OpenSSL-backed) so no native dependency is
added to the API image. Stored hashes are self-describing and versioned:

    pbkdf2_sha256$<iterations>$<salt-b64>$<hash-b64>

so a future move to a stronger KDF can re-hash lazily on successful login.
Password values must never be logged; use the masked-email helpers from
services.auth for any user-facing log line.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
# Sanity bounds when parsing a stored hash. Anything outside is treated as a
# corrupt/legacy value and simply fails verification (fail-closed).
MIN_STORED_ITERATIONS = 100_000
MAX_STORED_ITERATIONS = 2_000_000
SALT_BYTES = 16
DKLEN = 32

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64

_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")


def validate_password_strength(password: str) -> str | None:
    """Return a user-facing policy error message, or None when acceptable."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return f"密码至少需要 {PASSWORD_MIN_LENGTH} 个字符"
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"密码最长 {PASSWORD_MAX_LENGTH} 个字符"
    if not _HAS_LETTER.search(password) or not _HAS_DIGIT.search(password):
        return "密码需要同时包含字母和数字"
    return None


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=DKLEN)


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = _derive(password, salt, ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{ALGORITHM}${ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against a stored hash; malformed input fails closed."""
    if not password or not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != ALGORITHM:
        return False
    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected = base64.b64decode(parts[3].encode("ascii"))
    except (ValueError, TypeError):
        return False
    if not (MIN_STORED_ITERATIONS <= iterations <= MAX_STORED_ITERATIONS):
        return False
    if len(salt) < SALT_BYTES or not expected:
        return False
    candidate = _derive(password, salt, iterations)
    return hmac.compare_digest(candidate, expected)


def dummy_verify() -> None:
    """Burn one hash computation so missing accounts/passwords do not answer
    measurably faster than real ones (basic user-enumeration timing defense)."""
    _derive("timing-equalizer", b"0" * SALT_BYTES, MIN_STORED_ITERATIONS)
