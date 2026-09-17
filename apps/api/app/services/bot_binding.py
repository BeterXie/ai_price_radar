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
    bridge_session_id = None
    clawbot_qrcode = None
    clawbot_base_url = None

    # 1. First priority: Tencent iLink ClawBot Client (Official Tencent Bot, zero-auth, real QR friend addition)
    try:
        from extensions.bots.clawbot_client import ClawBotClient

        claw_client = ClawBotClient()
        claw_res = claw_client.start_qr_login()
        if claw_res and claw_res.get("qrcode_url"):
            qrcode_url = claw_res["qrcode_url"]
            clawbot_qrcode = claw_res.get("qrcode")
            clawbot_base_url = claw_client.base_url
    except Exception as exc:
        logger.debug("ClawBot QR not available: %s", exc)

    # 2. Check if QQ bot bridge connector QR is available
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
        "clawbot_qrcode": clawbot_qrcode,
        "clawbot_base_url": clawbot_base_url,
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
        "instruction": "请使用手机微信或 QQ 扫描二维码添加机器人并授权",
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

    # Check ClawBot status if session originated from ClawBot
    clawbot_qrcode = session.get("clawbot_qrcode")
    if clawbot_qrcode and db is not None:
        try:
            from extensions.bots.clawbot_client import ClawBotClient

            claw_client = ClawBotClient()
            claw_status = claw_client.poll_qr_status(clawbot_qrcode, base_url=session.get("clawbot_base_url"))
            st = str(claw_status.get("status") or "").lower()
            if st == "confirmed":
                bot_token = claw_status.get("bot_token") or ""
                target_id = claw_status.get("user_id") or claw_status.get("account_id") or "clawbot_friend"
                complete_qq_binding(db, session_id, target_id, bot_token=bot_token, channel="qq")
                if bot_token:
                    try:
                        claw_client.notify_start(bot_token, base_url=claw_status.get("base_url"))
                        claw_client.send_text(
                            bot_token,
                            target_id,
                            "🎉 绑定成功！您已成功连接 PriceMemo 机器人好友。\n"
                            "💡 常用指令：\n"
                            "  • plus — 查询 ChatGPT Plus 最低价(库存充足)\n"
                            "  • pro — 查询 Claude Pro 最低价\n"
                            "  • 降价 — 查看今日降价精选\n"
                            "  • 关注 — 查看您在 PriceMemo 关注的所有商品及最新价格\n"
                            "  • 行情 — 查看全网大盘报价",
                            base_url=claw_status.get("base_url"),
                        )
                    except Exception as e:
                        logger.warning("ClawBot notify_start or welcome failed: %s", e)
                return {
                    "status": "BOUND",
                    "bind_code": session["bind_code"],
                    "qrcode_url": session.get("qrcode_url", ""),
                    "target_id": target_id,
                    "message": "绑定成功，已与机器人成为好友！",
                }
            elif st == "scaned":
                session["status"] = "SCANNED"
                return {
                    "status": "SCANNED",
                    "bind_code": session["bind_code"],
                    "qrcode_url": session.get("qrcode_url", ""),
                    "message": "已扫码，请在手机上确认授权",
                }
            elif st in ("expired", "timeout"):
                return {"status": "EXPIRED", "message": "二维码已过期，请重新生成"}
        except Exception as exc:
            logger.debug("Error querying ClawBot QR status: %s", exc)

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
                    complete_qq_binding(db, session_id, target_id)
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


def complete_qq_binding(
    db: Session,
    bind_code_or_session: str,
    target_id: str,
    bot_token: str = "",
    channel: str = "qq",
) -> UserBotBinding | None:
    """Invoked when QQ Bot receives `/bind <code>` or bridge confirms binding."""
    found_key = None
    target_session = None

    for sid, sess in _PENDING_BINDINGS.items():
        if sess["bind_code"] == bind_code_or_session or sid == bind_code_or_session:
            if sess["expires_at"] > time.time():
                found_key = sid
                target_session = sess
                break

    if not target_session:
        return None

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
        binding.is_active = True
        binding.updated_at = now

    db.commit()
    db.refresh(binding)

    target_session["status"] = "BOUND"
    target_session["target_id"] = target_id
    logger.info("Successfully bound user %d to %s target %s", user_id, channel, target_id)
    return binding



def unbind_user_channel(db: Session, user_id: int, channel: str = "qq") -> bool:
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
