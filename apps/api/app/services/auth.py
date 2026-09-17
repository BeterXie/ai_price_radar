from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.email import normalize_email
from ..models import AuthCode, NotificationOutbox, User, UserActionLog, UserSession

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return utcnow()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_user_session(
    db: Session,
    user: User,
    settings: Settings | None = None,
    ip_address: str = "",
    user_agent: str = "",
) -> UserSession:
    settings = settings or get_settings()
    token = secrets.token_hex(32)
    now = utcnow()
    expires_at = now + timedelta(days=settings.session_max_age_days)
    session = UserSession(
        token=token,
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
    return session


def get_user_by_session_token(db: Session, token: str) -> User | None:
    if not token or len(token) < 32:
        return None
    now = utcnow()
    session = db.scalar(select(UserSession).where(UserSession.token == token))
    if session is None or ensure_utc(session.expires_at) <= now:
        return None
    if not session.user or not session.user.is_active:
        return None
    return session.user


def delete_user_session(db: Session, token: str) -> None:
    if not token:
        return
    session = db.scalar(select(UserSession).where(UserSession.token == token))
    if session:
        now = utcnow()
        duration = int((ensure_utc(session.last_active_at or now) - ensure_utc(session.created_at)).total_seconds())
        if duration > 0 and session.user:
            session.user.total_duration_seconds = (session.user.total_duration_seconds or 0) + duration
            log = UserActionLog(
                user_id=session.user_id,
                action_type="logout",
                action_name="用户退出登录",
                ip_address=session.ip_address or "",
                user_agent=session.user_agent or "",
                extra_data={"duration_seconds": duration},
                created_at=now,
            )
            db.add(log)
        db.delete(session)
        db.commit()


def send_email_login_code(db: Session, raw_email: str) -> tuple[bool, int, str]:
    """Generates 6-digit verification code and enqueues notification.

    Returns: (success, retry_after_seconds, message)
    """
    email = normalize_email(raw_email)
    if not EMAIL_REGEX.match(email):
        return False, 0, "请输入有效的邮箱地址"

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

    auth_code = AuthCode(
        email=email,
        code=code,
        purpose="login",
        expires_at=expires_at,
        used=False,
        created_at=now,
    )
    db.add(auth_code)

    # Enqueue in notification_outbox so existing worker / SMTP / Resend sends it
    outbox = NotificationOutbox(
        event_type="auth_login_code",
        recipient=email,
        subject="【PriceMemo】您的登录验证码",
        text_body=(
            f"您好！\n\n"
            f"您在 PriceMemo 比价雷达的登录验证码为：\n\n"
            f"    {code}\n\n"
            f"验证码有效期为 10 分钟。请勿将验证码泄露给他人。\n"
            f"如非您本人操作，请忽略此邮件。\n\n"
            f"—— PriceMemo 团队"
        ),
        dedupe_key=f"auth-code:{email}:{int(now.timestamp())}",
        status="pending",
        next_attempt_at=now,
    )
    db.add(outbox)
    db.commit()

    from .outbox import mail_is_configured

    settings = get_settings()
    if not mail_is_configured(settings):
        logger.warning(
            "[PriceMemo Dev Auth] 未配置邮件服务 (Resend/SMTP)，已在控制台打印验证码:\n"
            "--------------------------------------------------\n"
            "  目标邮箱: %s\n"
            "  登录验证码: %s (10分钟有效)\n"
            "--------------------------------------------------",
            email,
            code,
        )
        print(f"\n[PriceMemo Dev Auth] >>> 邮箱: {email} | 验证码: {code} <<<\n", flush=True)
    else:
        logger.info("Enqueued login code for %s (code: %s)", email, code)
    return True, 60, "验证码已发送至您的邮箱，请查收"


def verify_email_login_code(db: Session, raw_email: str, code: str) -> tuple[User | None, str]:
    email = normalize_email(raw_email)
    clean_code = code.strip()
    if not clean_code:
        return None, "请输入验证码"

    now = utcnow()
    auth_codes = list(
        db.scalars(
            select(AuthCode)
            .where(
                AuthCode.email == email,
                AuthCode.code == clean_code,
                AuthCode.purpose == "login",
                AuthCode.used == False,
            )
            .order_by(AuthCode.id.desc())
            .limit(1)
        )
    )
    auth_code = auth_codes[0] if auth_codes else None
    if auth_code is None or ensure_utc(auth_code.expires_at) <= now:
        return None, "验证码无效或已过期"

    auth_code.used = True

    # Find or create User
    user = db.scalar(select(User).where(User.email == email))
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
    db.commit()
    db.refresh(user)
    return user, ""


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
            me_data = eval(text_match.group(0)) if text_match else {}

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
