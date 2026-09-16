from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import AuthSessionResponse, EmailCodeRequest, EmailCodeResponse, EmailVerifyRequest, UserRead
from ..security import get_current_user, get_token_from_request
from ..services.auth import (
    build_qq_auth_url,
    create_user_session,
    delete_user_session,
    exchange_qq_oauth,
    find_or_create_qq_user,
    send_email_login_code,
    verify_email_login_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        nickname=user.nickname or (user.email.split("@")[0] if user.email else "用户"),
        avatar_url=user.avatar_url or "",
        has_qq_bound=bool(user.qq_openid),
        created_at=user.created_at,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    # 30 days in seconds
    max_age = settings.session_max_age_days * 86400
    is_secure = settings.web_origin.startswith("https://")
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )


@router.post("/email/code", response_model=EmailCodeResponse)
def request_email_code(
    payload: EmailCodeRequest,
    db: Session = Depends(get_db),
) -> EmailCodeResponse:
    success, retry_after, message = send_email_login_code(db, payload.email)
    if not success and retry_after > 0:
        return EmailCodeResponse(success=False, retry_after=retry_after, message=message)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return EmailCodeResponse(success=True, retry_after=retry_after, message=message)


@router.post("/email/verify", response_model=AuthSessionResponse)
def verify_email_code(
    payload: EmailVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    user, error_msg = verify_email_login_code(db, payload.email, payload.code)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg or "验证失败")

    session = create_user_session(db, user)
    _set_auth_cookie(response, session.token)

    return AuthSessionResponse(
        authenticated=True,
        user=_user_to_read(user),
        token=session.token,
    )


@router.get("/qq/login")
def qq_login_redirect(request: Request) -> Any:
    settings = get_settings()
    state = secrets.token_hex(16)

    # If QQ Auth is not configured or disabled:
    if not settings.qq_auth_enabled or not settings.qq_app_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QQ快捷登录暂未开放",
        )

    auth_url = build_qq_auth_url(state, settings)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/qq/callback")
def qq_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    mock: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> Any:
    settings = get_settings()

    # Handle local dev / mock mode
    if mock == "true" or not settings.qq_auth_enabled:
        mock_openid = f"mock_qq_{secrets.token_hex(8)}"
        if state and state.startswith("bind_"):
            from ..services.bot_binding import complete_qq_binding

            bind_session_id = state[5:]
            complete_qq_binding(db, bind_session_id, mock_openid)
            return RedirectResponse(url="/account?bind_success=1", status_code=status.HTTP_303_SEE_OTHER)

        if current_user is not None:
            user = current_user
            if not user.qq_openid:
                user.qq_openid = mock_openid
                db.commit()
                db.refresh(user)
        else:
            user = find_or_create_qq_user(db, openid=mock_openid, nickname="QQ体验用户")
        session = create_user_session(db, user)
        redir = RedirectResponse(url="/account?login_success=1", status_code=status.HTTP_303_SEE_OTHER)
        _set_auth_cookie(redir, session.token)
        return redir

    if not code:
        return RedirectResponse(url="/?auth_error=missing_code", status_code=status.HTTP_303_SEE_OTHER)

    try:
        identity = exchange_qq_oauth(code, settings)
        openid = identity["openid"]
        if state and state.startswith("bind_"):
            from ..services.bot_binding import complete_qq_binding

            bind_session_id = state[5:]
            complete_qq_binding(db, bind_session_id, openid)
            return RedirectResponse(url="/account?bind_success=1", status_code=status.HTTP_303_SEE_OTHER)

        if current_user is not None:
            user = current_user
            if not user.qq_openid:
                user.qq_openid = openid
            if identity.get("avatar_url") and not user.avatar_url:
                user.avatar_url = identity["avatar_url"]
            db.commit()
            db.refresh(user)
        else:
            user = find_or_create_qq_user(
                db,
                openid=openid,
                nickname=identity.get("nickname", ""),
                avatar_url=identity.get("avatar_url", ""),
            )
        session = create_user_session(db, user)
        redir = RedirectResponse(url="/account?login_success=1", status_code=status.HTTP_303_SEE_OTHER)
        _set_auth_cookie(redir, session.token)
        return redir
    except Exception as exc:
        logger.error("QQ OAuth callback error: %s", exc)
        return RedirectResponse(url="/?auth_error=qq_failed", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/qq/scan-mock", response_class=HTMLResponse)
def qq_scan_mock(
    session_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Mock endpoint for phone scanning test in dev mode."""
    from ..services.bot_binding import complete_qq_binding

    mock_openid = f"mock_qq_{secrets.token_hex(6)}"
    binding = complete_qq_binding(db, session_id, mock_openid)
    if binding is None:
        return HTMLResponse("<h3>❌ 绑定二维码已失效或已超时</h3><p>请在电脑端重新生成二维码</p>")
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>QQ 授权成功</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; margin: 0; background: #09090b; color: #f4f4f5; text-align: center; padding: 20px; }
        .card { background: #18181b; border: 1px solid #27272a; border-radius: 20px; padding: 32px 24px; max-width: 360px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
        .icon { font-size: 54px; margin-bottom: 16px; }
        h2 { margin: 0 0 8px 0; color: #10b981; font-size: 20px; }
        p { margin: 0; color: #a1a1aa; font-size: 14px; line-height: 1.6; }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">✅</div>
        <h2>QQ 授权扫码成功</h2>
        <p>您已成功在手机 QQ 完成对 PriceMemo 比价机器人的授权绑定！电脑网页已自动同步刷新。</p>
      </div>
    </body>
    </html>
    """)


@router.get("/me", response_model=AuthSessionResponse)
def get_me(
    current_user: User | None = Depends(get_current_user),
    request: Request = None,
) -> AuthSessionResponse:
    if current_user is None:
        return AuthSessionResponse(authenticated=False, user=None, token=None)
    token = get_token_from_request(request) if request else None
    return AuthSessionResponse(
        authenticated=True,
        user=_user_to_read(current_user),
        token=token,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    token = get_token_from_request(request)
    if token:
        delete_user_session(db, token)
    _clear_auth_cookie(response)
    return {"ok": True}
