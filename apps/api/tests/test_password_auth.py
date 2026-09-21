"""Tests for email + password authentication.

Covers the password KDF/policy helpers, first-login password setup, the
account-center change flow (current password required + other sessions
revoked), password login, generic error messaging (no user enumeration),
per-email failure throttling, and that no secret material leaks into
responses.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure repo root is in sys.path so extensions.bots can be imported if present
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import AuthCode, User, UserActionLog, UserSession
from app.services import auth as auth_service
from app.services.password_auth import (
    hash_password,
    validate_password_strength,
    verify_password,
)

GOOD_PASSWORD = "Radar2026x"
SECOND_PASSWORD = "Orbit7788y"


@pytest.fixture(autouse=True)
def enable_test_auth_codes(monkeypatch, bot_encryption_key):
    """This module reads login codes from its isolated database fixtures."""
    monkeypatch.setenv("DEV_PRINT_AUTH_CODES", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolated_password_throttle():
    auth_service._password_fail_buckets.clear()
    yield
    auth_service._password_fail_buckets.clear()


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _email_code_login(client: TestClient, test_db, email: str) -> dict:
    resp = client.post("/api/v1/auth/email/code", json={"email": email})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    code = test_db.scalar(
        select(AuthCode).where(AuthCode.email == email).order_by(AuthCode.id.desc())
    ).code
    resp = client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    return body


def _raw_session_login(test_db, user: User, client: TestClient) -> str:
    """Attach a legacy plaintext-token session cookie (as older tests do)."""
    token = secrets.token_hex(32)
    test_db.add(
        UserSession(
            token=token,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    test_db.commit()
    client.cookies.set("pm_session", token)
    return token


# ---------------------------------------------------------------------------
# Unit: KDF + policy helpers
# ---------------------------------------------------------------------------


def test_password_policy_validation():
    assert validate_password_strength("") is not None
    assert validate_password_strength("Ab1") is not None  # too short
    assert validate_password_strength("a" * 65) is not None  # too long
    assert validate_password_strength("abcdefgh") is not None  # no digit
    assert validate_password_strength("12345678") is not None  # no letter
    assert validate_password_strength(GOOD_PASSWORD) is None


def test_password_hash_verify_roundtrip():
    stored = hash_password(GOOD_PASSWORD)
    assert stored.startswith("pbkdf2_sha256$")
    assert GOOD_PASSWORD not in stored
    assert verify_password(GOOD_PASSWORD, stored) is True
    assert verify_password("wrong-password", stored) is False
    # Fail-closed on malformed / foreign formats
    assert verify_password(GOOD_PASSWORD, "") is False
    assert verify_password(GOOD_PASSWORD, "plaintext") is False
    assert verify_password(GOOD_PASSWORD, "bcrypt$12$aa$bb") is False
    assert verify_password(GOOD_PASSWORD, "pbkdf2_sha256$10$aa$bb") is False  # iterations below floor
    # Distinct salts produce distinct hashes for the same password
    assert hash_password(GOOD_PASSWORD) != stored


# ---------------------------------------------------------------------------
# Flow: first login sets a password, then password login works
# ---------------------------------------------------------------------------


def test_first_login_sets_password_then_password_login(client: TestClient, test_db):
    email = "newuser@example.com"
    session = _email_code_login(client, test_db, email)
    # Brand-new account has no password yet; frontend uses this flag to offer
    # the set-password step right after first login.
    assert session["user"]["has_password"] is False

    resp = client.post("/api/v1/user/password", json={"password": GOOD_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["has_password"] is True

    user = test_db.scalar(select(User).where(User.email == email))
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert GOOD_PASSWORD not in user.password_hash

    log = test_db.scalar(
        select(UserActionLog).where(UserActionLog.action_type == "password_set")
    )
    assert log is not None

    # Profile reflects the new state.
    me = client.get("/api/v1/user/profile").json()
    assert me["user"]["has_password"] is True

    # Password login now works from a fresh client (no cookie).
    fresh = TestClient(app)
    login = fresh.post(
        "/api/v1/auth/password/login",
        json={"email": email, "password": GOOD_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert login.json()["user"]["has_password"] is True
    # Session cookie was issued.
    assert fresh.cookies.get("pm_session")
    assert fresh.get("/api/v1/auth/me").json()["authenticated"] is True

    # Weak passwords are rejected and do not overwrite the existing hash.
    weak = client.post("/api/v1/user/password", json={
        "password": "alllower",
        "current_password": GOOD_PASSWORD,
    })
    assert weak.status_code == 200
    assert weak.json()["success"] is False
    assert "字母和数字" in weak.json()["message"]


def test_password_login_rejects_wrong_credentials_generically(client: TestClient, test_db):
    email = "member@example.com"
    _email_code_login(client, test_db, email)
    resp = client.post("/api/v1/user/password", json={"password": GOOD_PASSWORD})
    assert resp.json()["success"] is True

    # Wrong password, unknown account and passwordless account must all answer
    # with the same generic 400 so the endpoint is not an enumeration oracle.
    fresh = TestClient(app)
    wrong = fresh.post(
        "/api/v1/auth/password/login", json={"email": email, "password": "WrongPass123"}
    )
    unknown = fresh.post(
        "/api/v1/auth/password/login", json={"email": "ghost@example.com", "password": GOOD_PASSWORD}
    )
    passwordless_email = "codeonly@example.com"
    other_db_user = User(
        email=passwordless_email,
        nickname="code",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db.add(other_db_user)
    test_db.commit()
    passwordless = fresh.post(
        "/api/v1/auth/password/login", json={"email": passwordless_email, "password": GOOD_PASSWORD}
    )
    for res in (wrong, unknown, passwordless):
        assert res.status_code == 400
        assert res.json()["detail"] == "邮箱或密码错误"
    assert not fresh.cookies.get("pm_session")


def test_password_change_requires_current_and_revokes_other_sessions(test_db):
    email = "rotator@example.com"
    client_a = TestClient(app)
    client_b = TestClient(app)

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        _email_code_login(client_a, test_db, email)
        assert client_a.post("/api/v1/user/password", json={"password": GOOD_PASSWORD}).json()["success"] is True

        # Second device signs in with the password.
        login_b = client_b.post(
            "/api/v1/auth/password/login", json={"email": email, "password": GOOD_PASSWORD}
        )
        assert login_b.status_code == 200
        assert client_b.get("/api/v1/auth/me").json()["authenticated"] is True

        # Change without current password → rejected.
        missing = client_a.post("/api/v1/user/password", json={"password": SECOND_PASSWORD})
        assert missing.json()["success"] is False
        assert "当前密码" in missing.json()["message"]

        # Change with wrong current password → rejected.
        wrong = client_a.post("/api/v1/user/password", json={
            "password": SECOND_PASSWORD,
            "current_password": "NotMyPass1",
        })
        assert wrong.json()["success"] is False
        assert wrong.json()["message"] == "当前密码不正确"

        # Correct change → succeeds, and only the acting session survives.
        ok = client_a.post("/api/v1/user/password", json={
            "password": SECOND_PASSWORD,
            "current_password": GOOD_PASSWORD,
        })
        assert ok.json()["success"] is True
        assert "其他设备" in ok.json()["message"]

        assert client_a.get("/api/v1/auth/me").json()["authenticated"] is True
        assert client_b.get("/api/v1/auth/me").json()["authenticated"] is False

        # Old password no longer logs in; new one does.
        stale = TestClient(app).post(
            "/api/v1/auth/password/login", json={"email": email, "password": GOOD_PASSWORD}
        )
        assert stale.status_code == 400
        assert test_db.scalar(
            select(UserActionLog).where(UserActionLog.action_type == "password_change")
        ) is not None
    finally:
        app.dependency_overrides.clear()


def test_qq_only_account_cannot_set_password(client: TestClient, test_db):
    user = User(
        qq_openid="qq-openid-no-email",
        nickname="QQ用户",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db.add(user)
    test_db.commit()
    _raw_session_login(test_db, user, client)

    resp = client.post("/api/v1/user/password", json={"password": GOOD_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "未绑定邮箱" in body["message"]
    test_db.refresh(user)
    assert not user.password_hash


def test_per_email_failure_throttle_locks_then_success_clears(client: TestClient, test_db):
    email = "target@example.com"
    _email_code_login(client, test_db, email)
    assert client.post("/api/v1/user/password", json={"password": GOOD_PASSWORD}).json()["success"] is True
    client.post("/api/v1/auth/logout")

    fresh = TestClient(app)
    for _ in range(auth_service.PASSWORD_FAIL_MAX_ATTEMPTS):
        res = fresh.post(
            "/api/v1/auth/password/login", json={"email": email, "password": "BadGuess123"}
        )
        assert res.status_code == 400

    throttled = fresh.post(
        "/api/v1/auth/password/login", json={"email": email, "password": "BadGuess123"}
    )
    assert throttled.status_code == 429
    assert "验证码登录" in throttled.json()["detail"]

    # Even the correct password is refused while throttled (no probe shortcut).
    still_throttled = fresh.post(
        "/api/v1/auth/password/login", json={"email": email, "password": GOOD_PASSWORD}
    )
    assert still_throttled.status_code == 429

    # After the throttle clears, the correct password logs in and resets the bucket.
    auth_service.clear_password_failures(email.casefold())
    ok = fresh.post(
        "/api/v1/auth/password/login", json={"email": email, "password": GOOD_PASSWORD}
    )
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True
    assert auth_service._password_fail_buckets.get(email.casefold()) is None


def test_password_material_never_leaks_into_responses(client: TestClient, test_db):
    email = "leakcheck@example.com"
    _email_code_login(client, test_db, email)
    set_resp = client.post("/api/v1/user/password", json={"password": GOOD_PASSWORD})
    assert set_resp.json()["success"] is True
    user = test_db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash

    for path in ("/api/v1/auth/me", "/api/v1/user/profile"):
        text = client.get(path).text
        assert GOOD_PASSWORD not in text
        assert stored_hash not in text
        assert "password_hash" not in text
    assert GOOD_PASSWORD not in set_resp.text
    assert stored_hash not in set_resp.text
