from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import User, UserBotBinding

logger = logging.getLogger(__name__)

# In-memory temporary binding tokens: token -> {user_id, expires_at, qrcode_url, ...}
_PENDING_BINDINGS: dict[str, dict[str, Any]] = {}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_qq_binding_session(user_id: int) -> dict[str, Any]:
    """Generate a temporary QR session and code for the user to bind their QQ."""
    now = time.time()
    # Clean up expired
    expired = [k for k, v in _PENDING_BINDINGS.items() if v["expires_at"] < now]
    for k in expired:
        _PENDING_BINDINGS.pop(k, None)

    # 6-digit verification code
    bind_code = f"{secrets.randbelow(900000) + 100000}"
    session_id = secrets.token_hex(16)
    expires_at = now + 300  # 5 minutes for QR code

    settings = get_settings()
    qrcode_url = ""
    qq_task_id = None
    qq_key = None
    bridge_session_id = None

    # 1. First priority: Tencent QQ Connector (Official QQ OpenClaw zero-auth mobile QQ connect)
    # Reference: Dota AI Decision Lab (@tencent-connect/qqbot-connector)
    try:
        from extensions.bots.qq_connector import QQConnectorClient

        connector = QQConnectorClient()
        conn_res = connector.start_bind_task()
        if conn_res and conn_res.get("qrcode_url"):
            qrcode_url = conn_res["qrcode_url"]
            qq_task_id = conn_res.get("task_id")
            qq_key = conn_res.get("key")
    except Exception as exc:
        logger.debug("QQ Connector not available: %s", exc)

    # 2. Check if QQ bot bridge connector QR is available (Dota AI Decision Lab Node bridge)
    if not qrcode_url:
        try:
            from extensions.bots.qq_bot import QQBotClient

            bot_client = QQBotClient()
            bridge_res = bot_client.start_qr_session()
            if bridge_res and bridge_res.get("qrcode_url"):
                qrcode_url = bridge_res["qrcode_url"]
                bridge_session_id = bridge_res.get("session_id")
        except Exception as exc:
            logger.debug("QQ bot bridge QR not available: %s", exc)

    # 3. Fallback to Tencent QQ OAuth QR if configured
    if not qrcode_url:
        if settings.qq_auth_enabled and settings.qq_app_id:
            from .auth import build_qq_auth_url

            qrcode_url = build_qq_auth_url(f"bind_{session_id}", settings)

    _PENDING_BINDINGS[session_id] = {
        "user_id": user_id,
        "bind_code": bind_code,
        "qrcode_url": qrcode_url,
        "qq_task_id": qq_task_id,
        "qq_key": qq_key,
        "bridge_session_id": bridge_session_id,
        "expires_at": expires_at,
        "status": "WAITING",
        "target_id": None,
    }

    return {
        "session_id": session_id,
        "bind_code": bind_code,
        "qrcode_url": qrcode_url,
        "expires_in_seconds": 300,
        "instruction": "请使用手机 QQ 扫描二维码添加机器人并授权",
    }


def check_qq_binding_session(session_id: str, db: Session | None = None) -> dict[str, Any]:
    session = _PENDING_BINDINGS.get(session_id)
    if not session:
        return {"status": "EXPIRED", "message": "绑定会话不存在或已失效"}
    if time.time() > session["expires_at"]:
        _PENDING_BINDINGS.pop(session_id, None)
        return {"status": "EXPIRED", "message": "二维码已过期，请点击刷新"}

    # If already marked BOUND
    if session.get("status") == "BOUND":
        return {
            "status": "BOUND",
            "bind_code": session["bind_code"],
            "qrcode_url": session.get("qrcode_url", ""),
            "target_id": session.get("target_id"),
            "message": "绑定成功",
        }

    # Check QQ Connector status if session originated from QQ Connector
    qq_task_id = session.get("qq_task_id")
    qq_key = session.get("qq_key")
    if qq_task_id and qq_key and db is not None:
        try:
            from extensions.bots.qq_connector import QQConnectorClient

            connector = QQConnectorClient()
            res = connector.poll_bind_task(qq_task_id, qq_key)
            st = res.get("status")
            if st == "COMPLETED":
                app_id = res.get("app_id") or ""
                app_secret = res.get("app_secret") or ""
                user_openid = res.get("user_openid") or ""
                complete_qq_binding(
                    db,
                    session_id,
                    target_id=user_openid,
                    bot_token=app_secret,
                    extra_meta={"app_id": app_id, "user_openid": user_openid},
                    channel="qq",
                )
                try:
                    from extensions.bots.qq_bot import QQBotClient

                    bot_client = QQBotClient(app_id=app_id, app_secret=app_secret)
                    welcome_msg = (
                        "🎉 恭喜！您已成功连接 PriceMemo QQ 机器人好友。\n"
                        "💡 常用指令：\n"
                        "  • plus — 查询 ChatGPT Plus 最低价(库存充足)\n"
                        "  • pro — 查询 Claude Pro 最低价\n"
                        "  • 降价 — 查看今日降价精选\n"
                        "  • 关注 — 查看您在 PriceMemo 关注的全部商品及最新价格\n"
                        "  • 行情 — 查看全网大盘报价"
                    )
                    bot_client.send_c2c_message(user_openid, welcome_msg, app_id=app_id, app_secret=app_secret)
                except Exception as e:
                    logger.warning("Failed sending QQ welcome message: %s", e)

                return {
                    "status": "BOUND",
                    "bind_code": session["bind_code"],
                    "qrcode_url": session.get("qrcode_url", ""),
                    "target_id": user_openid,
                    "message": "绑定成功！已成功连接手机 QQ 机器人。",
                }
            elif st == "EXPIRED":
                return {"status": "EXPIRED", "message": "二维码已过期，请重新生成"}
        except Exception as exc:
            logger.debug("Error querying QQ connector status: %s", exc)

    # Check bridge status if session originated from bridge
    bridge_session_id = session.get("bridge_session_id")
    if bridge_session_id and db is not None:
        try:
            from extensions.bots.qq_bot import QQBotClient

            bot_client = QQBotClient()
            bridge_status = bot_client.check_qr_session(bridge_session_id)
            if bridge_status:
                b_status = bridge_status.get("status")
                if b_status in ("COMPLETED", "BOUND"):
                    creds = bridge_status.get("credentials") or {}
                    target_id = creds.get("user_openid") or creds.get("app_id") or "qq_bound_user"
                    app_id = creds.get("app_id") or ""
                    app_secret = creds.get("app_secret") or ""
                    complete_qq_binding(
                        db,
                        session_id,
                        target_id,
                        bot_token=app_secret,
                        extra_meta={"app_id": app_id, "user_openid": target_id},
                        channel="qq",
                    )
                    return {

                        "status": "BOUND",
                        "bind_code": session["bind_code"],
                        "qrcode_url": session.get("qrcode_url", ""),
                        "target_id": target_id,
                        "message": "绑定成功",
                    }
                elif b_status == "EXPIRED":
                    return {"status": "EXPIRED", "message": "二维码已过期，请重新生成"}
        except Exception as exc:
            logger.debug("Error querying bridge QR status: %s", exc)

    return {
        "status": session["status"],
        "bind_code": session["bind_code"],
        "qrcode_url": session.get("qrcode_url", ""),
        "target_id": session.get("target_id"),
    }



def bind_current_user_qq(db: Session, user: User) -> UserBotBinding | None:
    """One-click binding when user is already authenticated via QQ."""
    if not user.qq_openid:
        return None

    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.user_id == user.id,
            UserBotBinding.channel == "qq",
        )
    )
    now = utcnow()
    if binding is None:
        binding = UserBotBinding(
            user_id=user.id,
            channel="qq",
            target_id=user.qq_openid,
            is_active=True,
            notify_price_drop=True,
            notify_price_hike=True,
            created_at=now,
            updated_at=now,
        )
        db.add(binding)
    else:
        binding.target_id = user.qq_openid
        binding.is_active = True
        binding.updated_at = now

    db.commit()
    db.refresh(binding)
    return binding


def _find_pending_binding(bind_code_or_session: str) -> tuple[str, dict[str, Any]] | None:
    for sid, sess in _PENDING_BINDINGS.items():
        if sess["bind_code"] == bind_code_or_session or sid == bind_code_or_session:
            if sess["expires_at"] > time.time():
                return sid, sess
    return None


def complete_qq_binding(
    db: Session,
    bind_code_or_session: str,
    target_id: str,
    bot_token: str = "",
    extra_meta: dict | None = None,
    channel: str = "qq",
) -> UserBotBinding | None:
    """Invoked when QQ Bot receives `/bind <code>` or bridge confirms binding."""
    found = _find_pending_binding(bind_code_or_session)
    if not found:
        return None
    found_key, target_session = found

    # One-time consumption: an already-completed session must never mutate the
    # binding again (replaying an old code must not redirect notifications).
    if target_session.get("status") == "BOUND":
        return db.scalar(
            select(UserBotBinding).where(
                UserBotBinding.user_id == target_session["user_id"],
                UserBotBinding.channel == channel,
            )
        )

    user_id = target_session["user_id"]
    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.user_id == user_id,
            UserBotBinding.channel == channel,
        )
    )
    now = utcnow()
    if binding is None:
        binding = UserBotBinding(
            user_id=user_id,
            channel=channel,
            target_id=target_id,
            bot_token=bot_token,
            extra_meta=extra_meta or {},
            is_active=True,
            notify_price_drop=True,
            notify_price_hike=True,
            created_at=now,
            updated_at=now,
        )
        db.add(binding)
    else:
        binding.target_id = target_id
        if bot_token:
            binding.bot_token = bot_token
        if extra_meta:
            binding.extra_meta = extra_meta
        binding.is_active = True
        binding.updated_at = now


    db.commit()
    db.refresh(binding)

    target_session["status"] = "BOUND"
    target_session["target_id"] = target_id
    logger.info("Successfully bound user %d to %s target %s", user_id, channel, target_id)
    return binding


def complete_qq_binding_for_user(
    db: Session,
    user: User,
    bind_code: str,
    target_id: str,
    channel: str = "qq",
) -> tuple[UserBotBinding | None, str]:
    """Manual confirm entry for the logged-in owner of the binding session.

    Unlike complete_qq_binding (trusted bot/connector callbacks), this path
    validates that the pending session belongs to the caller and that the
    requested target is not already bound to a different account.
    Returns (binding, error_message).
    """
    target_id = (target_id or "").strip()
    if not target_id:
        return None, "请输入要绑定的 QQ 标识"

    found = _find_pending_binding(bind_code)
    if not found:
        return None, "绑定码无效或已失效"
    _found_key, session = found
    if session.get("user_id") != user.id:
        # Never let one user complete another user's pending binding session.
        return None, "绑定码无效或已失效"
    if session.get("status") == "BOUND":
        existing = db.scalar(
            select(UserBotBinding).where(
                UserBotBinding.user_id == user.id,
                UserBotBinding.channel == channel,
            )
        )
        if existing is not None:
            return existing, ""

    collision = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == channel,
            UserBotBinding.target_id == target_id,
            UserBotBinding.user_id != user.id,
        )
    )
    if collision is not None:
        return None, "该 QQ 已被其他账号绑定"

    binding = complete_qq_binding(db, bind_code, target_id, channel=channel)
    if binding is None:
        return None, "绑定码无效或已失效"
    return binding, ""



def unbind_user_channel(db: Session, user_id: int, channel: str = "qq") -> bool:
    # Revoke any pending binding sessions for this user so stale codes
    # cannot re-establish a binding after the user explicitly unbound.
    for sid, sess in list(_PENDING_BINDINGS.items()):
        if sess.get("user_id") == user_id:
            _PENDING_BINDINGS.pop(sid, None)

    result = db.execute(
        delete(UserBotBinding).where(
            UserBotBinding.user_id == user_id,
            UserBotBinding.channel == channel,
        )
    )
    db.commit()
    return bool(result.rowcount and result.rowcount > 0)


def update_binding_preferences(
    db: Session,
    user_id: int,
    channel: str = "qq",
    *,
    is_active: bool | None = None,
    notify_price_drop: bool | None = None,
    notify_price_hike: bool | None = None,
) -> UserBotBinding | None:
    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.user_id == user_id,
            UserBotBinding.channel == channel,
        )
    )
    if binding is None:
        return None

    if is_active is not None:
        binding.is_active = is_active
    if notify_price_drop is not None:
        binding.notify_price_drop = notify_price_drop
    if notify_price_hike is not None:
        binding.notify_price_hike = notify_price_hike
    binding.updated_at = utcnow()
    db.commit()
    db.refresh(binding)
    return binding


def get_user_bindings(db: Session, user_id: int) -> list[UserBotBinding]:
    return list(db.scalars(select(UserBotBinding).where(UserBotBinding.user_id == user_id)))
