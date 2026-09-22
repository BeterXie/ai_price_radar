from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.email import normalize_email
from ..models import AuthCode, NotificationOutbox, User, UserActionLog, UserSession

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_VERIFY_ATTEMPTS = 5
_VERIFY_RATE_WINDOW_SECONDS = 60
_VERIFY_RATE_MAX_REQUESTS = 20
_verify_rate_lock = threading.Lock()
_verify_rate_buckets: dict[str, deque[float]] = {}
_email_issue_lock = threading.Lock()

# Per-email password failure throttle. Complements the persistent per-IP DB
# limiter on the login endpoint: the IP limiter stops volume attacks from one
# source, this one slows targeted guessing against a single account even when
# the attacker rotates sources. In-process like the verify limiter above (the
# API runs one uvicorn process per container); only failed attempts count and
# a success clears the bucket.
PASSWORD_FAIL_WINDOW_SECONDS = 600
PASSWORD_FAIL_MAX_ATTEMPTS = 5
_password_fail_lock = threading.Lock()
_password_fail_buckets: dict[str, deque[float]] = {}


def check_password_failure_throttle(email: str) -> bool:
    """Return False when this email has too many recent password failures."""
    if not email:
        return True
    now = time.monotonic()
    with _password_fail_lock:
        bucket = _password_fail_buckets.get(email)
        if not bucket:
            return True
        while bucket and now - bucket[0] > PASSWORD_FAIL_WINDOW_SECONDS:
            bucket.popleft()
        return len(bucket) < PASSWORD_FAIL_MAX_ATTEMPTS


def record_password_failure(email: str) -> None:
    if not email:
        return
    now = time.monotonic()
    with _password_fail_lock:
        bucket = _password_fail_buckets.setdefault(email, deque())
        while bucket and now - bucket[0] > PASSWORD_FAIL_WINDOW_SECONDS:
            bucket.popleft()
        bucket.append(now)
        # Opportunistic cleanup to bound memory (same policy as verify buckets).
        if len(_password_fail_buckets) > 10000:
            stale = [k for k, v in _password_fail_buckets.items() if not v or now - v[-1] > 3600]
            for k in stale:
                _password_fail_buckets.pop(k, None)


def clear_password_failures(email: str) -> None:
    if not email:
        return
    with _password_fail_lock:
        _password_fail_buckets.pop(email, None)


def _check_verify_rate_limit(client_ip: str) -> bool:
    """Simple in-process sliding-window limiter for verification attempts."""
    if not client_ip:
        return True
    now = time.monotonic()
    with _verify_rate_lock:
        bucket = _verify_rate_buckets.setdefault(client_ip, deque())
        while bucket and now - bucket[0] > _VERIFY_RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _VERIFY_RATE_MAX_REQUESTS:
            return False
        bucket.append(now)
        # Opportunistic cleanup to bound memory
        if len(_verify_rate_buckets) > 10000:
            stale = [k for k, v in _verify_rate_buckets.items() if not v or now - v[-1] > 3600]
            for k in stale:
                _verify_rate_buckets.pop(k, None)
        return True


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return utcnow()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _session_token_digest(raw_token: str) -> str:
    """Return a non-reversible, URL-safe digest for database storage."""
    digest = hashlib.sha256(raw_token.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def get_session_by_token(db: Session, raw_token: str) -> UserSession | None:
    """Resolve raw session tokens while allowing existing plaintext rows to expire naturally."""
    if not raw_token or len(raw_token) != 64:
        return None
    digest = _session_token_digest(raw_token)
    return db.scalar(select(UserSession).where(UserSession.token.in_((digest, raw_token))))


def get_issued_session_token(session: UserSession) -> str:
    raw_token = getattr(session, "_raw_token", "")
    if not raw_token:
        raise RuntimeError("raw session token is only available immediately after issuance")
    return raw_token


def migrate_legacy_session_tokens(db: Session) -> int:
    """Hash legacy 64-character plaintext session rows without invalidating clients."""
    changed = 0
    for session in db.scalars(select(UserSession)).all():
        stored = session.token or ""
        if len(stored) == 64 and all(ch in "0123456789abcdef" for ch in stored.casefold()):
            session.token = _session_token_digest(stored)
            changed += 1
    if changed:
        db.commit()
    return changed


def create_user_session(
    db: Session,
    user: User,
    settings: Settings | None = None,
    ip_address: str = "",
    user_agent: str = "",
) -> UserSession:
    settings = settings or get_settings()
    raw_token = secrets.token_hex(32)
    stored_token = _session_token_digest(raw_token)
    now = utcnow()
    expires_at = now + timedelta(days=settings.session_max_age_days)
    session = UserSession(
        token=stored_token,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        last_active_at=now,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(session)
    user.last_login_at = now
    if ip_address:
        user.last_login_ip = ip_address
    user.last_active_at = now
    log = UserActionLog(
        user_id=user.id,
        action_type="login",
        action_name="用户登录",
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(session)
    session._raw_token = raw_token
    return session


def get_user_by_session_token(db: Session, token: str) -> User | None:
    session = get_session_by_token(db, token)
    if session is None:
        return None
    now = utcnow()
    if session is None or ensure_utc(session.expires_at) <= now:
        return None
    if not session.user or not session.user.is_active:
        return None
    return session.user


def settle_session_activity(
    db: Session,
    user: User,
    session: UserSession | None,
    now: datetime | None = None,
) -> None:
    """Settle online-duration accounting against the session's last activity time.

    All activity entry points (heartbeat, clicks, logout) must go through this
    helper so that seconds are only ever accumulated once, from a single
    baseline (session.last_active_at), and idle gaps never count as online time.
    """
    if user is None:
        return
    now = ensure_utc(now or utcnow())
    if session is not None:
        stored_baseline = session.last_active_at
        baseline = stored_baseline or session.created_at
        baseline_filter = (
            UserSession.last_active_at.is_(None)
            if stored_baseline is None
            else UserSession.last_active_at == stored_baseline
        )
        claimed = db.execute(
            update(UserSession)
            .where(UserSession.token == session.token, baseline_filter)
            .values(last_active_at=now)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            db.expire(session, ["last_active_at"])
            db.expire(user, ["last_active_at", "total_duration_seconds"])
            return

        delta = int((now - ensure_utc(baseline)).total_seconds())
        duration_increment = delta if 5 <= delta <= 120 else 0
        db.execute(
            update(User)
            .where(User.id == user.id)
            .values(
                total_duration_seconds=func.coalesce(User.total_duration_seconds, 0) + duration_increment,
                last_active_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        db.expire(session, ["last_active_at"])
        db.expire(user, ["last_active_at", "total_duration_seconds"])
        return

    stored_baseline = user.last_active_at
    baseline_filter = (
        User.last_active_at.is_(None)
        if stored_baseline is None
        else User.last_active_at == stored_baseline
    )
    delta = int((now - ensure_utc(stored_baseline)).total_seconds()) if stored_baseline else 0
    duration_increment = delta if 5 <= delta <= 120 else 0
    db.execute(
        update(User)
        .where(User.id == user.id, baseline_filter)
        .values(
            total_duration_seconds=func.coalesce(User.total_duration_seconds, 0) + duration_increment,
            last_active_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.expire(user, ["last_active_at", "total_duration_seconds"])


def delete_user_session(db: Session, token: str) -> None:
    session = get_session_by_token(db, token)
    if session:
        now = utcnow()
        if session.user:
            # Only settle the (small) interval not yet accumulated by heartbeats;
            # the rest of the session span was already counted incrementally.
            settle_session_activity(db, session.user, session, now=now)
            log = UserActionLog(
                user_id=session.user_id,
                action_type="logout",
                action_name="用户退出登录",
                ip_address=session.ip_address or "",
                user_agent=session.user_agent or "",
                created_at=now,
            )
            db.add(log)
        db.delete(session)
        db.commit()


def _masked_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "***"
    visible = local[:1]
    return f"{visible}***@{domain}"


def _send_email_login_code_locked(
    db: Session,
    email: str,
    *,
    scene: str = "login",
    mail_ready: bool,
    settings: Settings,
) -> tuple[bool, int, str]:
    now = utcnow()
    # Check if a code was sent in the last 60 seconds
    recent_codes = list(
        db.scalars(
            select(AuthCode)
            .where(
                AuthCode.email == email,
                AuthCode.purpose == "login",
            )
            .order_by(AuthCode.id.desc())
            .limit(1)
        )
    )
    recent_code = recent_codes[0] if recent_codes else None
    if recent_code is not None:
        elapsed = int((now - ensure_utc(recent_code.created_at)).total_seconds())
        if elapsed < 60:
            retry_after = max(1, 60 - elapsed)
            return False, retry_after, f"验证码发送过于频繁，请在 {retry_after} 秒后重试"

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = now + timedelta(minutes=10)

    # Issuing a new code must revoke every older active code for this address.
    db.execute(
        update(AuthCode)
        .where(
            AuthCode.email == email,
            AuthCode.purpose == "login",
            AuthCode.used.is_(False),
        )
        .values(used=True)
    )

    auth_code = AuthCode(
        email=email,
        code=code,
        purpose="login",
        expires_at=expires_at,
        used=False,
        created_at=now,
    )
    db.add(auth_code)

    if scene == "shop":
        subject = "【彩头软件】官方移动端商城服务开通验证码"
        text_body = (
            f"尊敬的用户：\n\n"
            f"您好！\n\n"
            f"您正在 湖南湘江新区彩头软件开发工作室 官方移动端商城（shop.pricememo.cn）办理技术服务订购与开通核验，您的验证码为：\n\n"
            f"    {code}\n\n"
            f"验证码有效期为 10 分钟。请勿将验证码泄露给他人。\n"
            f"如非您本人操作，请忽略此邮件。\n\n"
            f"—— 湖南湘江新区彩头软件开发工作室"
        )
    else:
        subject = "【PriceMemo】您的登录验证码"
        text_body = (
            f"您好！\n\n"
            f"您在 PriceMemo 比价雷达的登录验证码为：\n\n"
            f"    {code}\n\n"
            f"验证码有效期为 10 分钟。请勿将验证码泄露给他人。\n"
            f"如非您本人操作，请忽略此邮件。\n\n"
            f"—— PriceMemo 团队"
        )

    # Enqueue in notification_outbox so existing worker / SMTP / Resend sends it
    outbox = NotificationOutbox(
        event_type="auth_login_code",
        recipient=email,
        subject=subject,
        text_body=text_body,
        dedupe_key=f"auth-code:{email}:{int(now.timestamp())}",
        status="pending",
        next_attempt_at=now,
    )
    db.add(outbox)
    db.commit()

    if not mail_ready:
        if settings.dev_print_auth_codes:
            logger.warning(
                "[PriceMemo Dev Auth] 未配置邮件服务 (Resend/SMTP)，已在控制台打印验证码:\n"
                "--------------------------------------------------\n"
                "  目标邮箱: %s\n"
                "  登录验证码: %s (10分钟有效)\n"
                "--------------------------------------------------",
                _masked_email(email),
                code,
            )
            print(
                f"\n[PriceMemo Dev Auth] >>> 邮箱: {_masked_email(email)} | 验证码: {code} <<<\n",
                flush=True,
            )
        else:
            logger.warning(
                "Mail service is not configured and dev_print_auth_codes is disabled; "
                "login code for %s was enqueued but cannot be delivered.",
                _masked_email(email),
            )
    else:
        # Never log the code itself in production logs.
        logger.info("Enqueued login code for %s", _masked_email(email))
    return True, 60, "验证码已发送至您的邮箱，请查收"


def send_email_login_code(db: Session, raw_email: str, scene: str = "login") -> tuple[bool, int, str]:
    """Generate one login code under a per-address database serialization lock."""
    try:
        email = normalize_email(raw_email)
    except ValueError:
        return False, 0, "请输入有效的邮箱地址"
    if not EMAIL_REGEX.match(email):
        return False, 0, "请输入有效的邮箱地址"

    from .outbox import mail_is_configured

    settings = get_settings()
    mail_ready = mail_is_configured(settings)
    if not mail_ready and not settings.dev_print_auth_codes:
        return False, 0, "邮件服务暂未配置，暂时无法发送验证码"

    with _email_issue_lock:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                {"identity": f"auth-email-code\n{email}"},
            )
        return _send_email_login_code_locked(
            db,
            email,
            scene=scene,
            mail_ready=mail_ready,
            settings=settings,
        )


def verify_email_login_code(
    db: Session,
    raw_email: str,
    code: str,
    client_ip: str = "",
) -> tuple[User | None, str]:
    try:
        email = normalize_email(raw_email)
    except ValueError:
        return None, "请输入有效的邮箱地址"
    clean_code = code.strip()
    if not clean_code:
        return None, "请输入验证码"
    if not _check_verify_rate_limit(client_ip):
        return None, "尝试过于频繁，请稍后再试"

    now = utcnow()
    # Load the latest active code for this email regardless of the entered value,
    # so failed guesses can be counted and throttled per code.
    auth_code = db.scalar(
        select(AuthCode)
        .where(
            AuthCode.email == email,
            AuthCode.purpose == "login",
            AuthCode.used == False,
        )
        .order_by(AuthCode.id.desc())
        .limit(1)
    )
    if auth_code is None or ensure_utc(auth_code.expires_at) <= now:
        return None, "验证码无效或已过期"

    if not hmac.compare_digest(auth_code.code, clean_code):
        # Increment inside the database so concurrent guesses consume one shared
        # budget instead of repeatedly writing the same stale counter value.
        updated = db.execute(
            update(AuthCode)
            .where(AuthCode.id == auth_code.id, AuthCode.used.is_(False))
            .values(attempts=func.coalesce(AuthCode.attempts, 0) + 1)
        )
        if updated.rowcount != 1:
            db.rollback()
            return None, "验证码无效或已过期"
        attempts = db.scalar(select(AuthCode.attempts).where(AuthCode.id == auth_code.id)) or 0
        if attempts >= MAX_VERIFY_ATTEMPTS:
            db.execute(
                update(AuthCode)
                .where(AuthCode.id == auth_code.id, AuthCode.used.is_(False))
                .values(used=True)
            )
        db.commit()
        return None, "验证码错误或已失效"

    # Atomic consumption: only one concurrent request can flip used=False -> True.
    consumed = db.execute(
        update(AuthCode)
        .where(AuthCode.id == auth_code.id, AuthCode.used == False)
        .values(used=True)
    )
    if consumed.rowcount != 1:
        return None, "验证码无效或已过期"

    # Find or create User
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        nickname = email.split("@")[0][:30]
        user = User(
            email=email,
            nickname=nickname,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
    elif user.email != email:
        user.email = email
    db.commit()
    db.refresh(user)
    return user, ""


def authenticate_with_password(db: Session, raw_email: str, password: str) -> User | None:
    """Resolve a user by email + password.

    Returns None for unknown addresses, accounts without a password set, wrong
    passwords and deactivated users. Missing accounts and passwordless accounts
    burn one dummy hash so response timing does not reveal which case applied.
    """
    from .password_auth import dummy_verify, verify_password

    try:
        email = normalize_email(raw_email)
    except ValueError:
        return None
    if not EMAIL_REGEX.match(email) or not password:
        return None

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not (user.password_hash or ""):
        dummy_verify()
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def build_qq_auth_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    redirect_uri = settings.qq_redirect_uri or f"{settings.web_origin}/api/v1/auth/qq/callback"
    params = {
        "response_type": "code",
        "client_id": settings.qq_app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "get_user_info",
    }
    return f"https://graph.qq.com/oauth2.0/authorize?{urlencode(params)}"


def exchange_qq_oauth(code: str, settings: Settings | None = None) -> dict[str, Any]:
    """Exchange QQ auth code for openid and userinfo via Tencent Graph API."""
    settings = settings or get_settings()
    redirect_uri = settings.qq_redirect_uri or f"{settings.web_origin}/api/v1/auth/qq/callback"

    token_url = "https://graph.qq.com/oauth2.0/token"
    token_params = {
        "grant_type": "authorization_code",
        "client_id": settings.qq_app_id,
        "client_secret": settings.qq_app_key,
        "code": code,
        "redirect_uri": redirect_uri,
        "fmt": "json",
    }

    with httpx.Client(timeout=15.0) as client:
        token_resp = client.get(token_url, params=token_params)
        try:
            token_data = token_resp.json()
        except Exception:
            token_data = {k: v[0] for k, v in parse_qs(token_resp.text).items()}

        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError(f"Failed to obtain QQ access token: {token_resp.text}")

        # Get OpenID
        me_url = "https://graph.qq.com/oauth2.0/me"
        me_resp = client.get(me_url, params={"access_token": access_token, "fmt": "json"})
        try:
            me_data = me_resp.json()
        except Exception:
            # Handle callback( { ... } );
            text_match = re.search(r"\{.*\}", me_resp.text)
            me_data = json.loads(text_match.group(0)) if text_match else {}

        openid = me_data.get("openid")
        if not openid:
            raise RuntimeError(f"Failed to obtain QQ OpenID: {me_resp.text}")

        # Get User Info
        user_info_url = "https://graph.qq.com/user/get_user_info"
        info_resp = client.get(
            user_info_url,
            params={
                "access_token": access_token,
                "oauth_consumer_key": settings.qq_app_id,
                "openid": openid,
            },
        )
        info_data = info_resp.json() if info_resp.status_code == 200 else {}

        return {
            "openid": openid,
            "nickname": str(info_data.get("nickname") or "QQ用户"),
            "avatar_url": str(info_data.get("figureurl_qq_2") or info_data.get("figureurl_2") or ""),
        }


def find_or_create_qq_user(db: Session, openid: str, nickname: str = "", avatar_url: str = "") -> User:
    now = utcnow()
    user = db.scalar(select(User).where(User.qq_openid == openid))
    if user is None:
        user = User(
            qq_openid=openid,
            nickname=nickname or "QQ用户",
            avatar_url=avatar_url or "",
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if nickname and not user.nickname:
            user.nickname = nickname
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        db.commit()
        db.refresh(user)
    return user
