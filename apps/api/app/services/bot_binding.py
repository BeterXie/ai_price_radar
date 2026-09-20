from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import QQBindingSession, ReportRateLimit, User, UserBotBinding
from .credential_crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

_BIND_ATTEMPT_WINDOW_SECONDS = 300
_BIND_ATTEMPT_MAX = 10


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _advisory_lock(db: Session, namespace: str, value: str) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).digest()
    key = int.from_bytes(digest[:8], "big", signed=False)
    if key >= 2**63:
        key -= 2**64
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _allow_binding_attempt(db: Session, target_id: str) -> bool:
    """Persist bot-side bind guess limits so multiple workers share one budget."""
    target = (target_id or "").strip()
    if not target:
        return False
    client_key = hashlib.sha256(f"qq-bind:{target}".encode("utf-8")).hexdigest()
    _advisory_lock(db, "qq-bind-rate", target)
    now = utcnow()
    window = timedelta(seconds=_BIND_ATTEMPT_WINDOW_SECONDS)
    rate = db.get(ReportRateLimit, client_key)
    if rate is None:
        db.add(ReportRateLimit(client_key=client_key, window_started_at=now, request_count=1))
    else:
        started = _ensure_utc(rate.window_started_at)
        if now - started >= window:
            rate.window_started_at = now
            rate.request_count = 1
        elif rate.request_count >= _BIND_ATTEMPT_MAX:
            db.rollback()
            return False
        else:
            rate.request_count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def _find_pending_binding(db: Session, bind_code_or_session: str) -> QQBindingSession | None:
    now = utcnow()
    return db.scalar(
        select(QQBindingSession).where(
            or_(
                QQBindingSession.session_id == bind_code_or_session,
                QQBindingSession.bind_code == bind_code_or_session,
            ),
            QQBindingSession.expires_at > now,
        )
    )


def _session_status(session: QQBindingSession) -> dict[str, Any]:
    visible_status = "WAITING" if session.status == "CLAIMING" else session.status
    return {
        "status": visible_status,
        "bind_code": session.bind_code,
        "qrcode_url": session.qrcode_url or "",
        "target_id": session.target_id or None,
    }


def start_qq_binding_session(db: Session, user_id: int) -> dict[str, Any]:
    """Generate and persist a temporary binding session shared by all API workers."""
    now = utcnow()
    expires_at = now + timedelta(minutes=5)

    db.execute(delete(QQBindingSession).where(QQBindingSession.expires_at <= now))
    db.execute(
        delete(QQBindingSession).where(
            QQBindingSession.user_id == user_id,
            QQBindingSession.status.in_(("WAITING", "CLAIMING", "EXPIRED")),
        )
    )

    bind_code = ""
    for _ in range(10):
        candidate = f"{secrets.randbelow(90_000_000) + 10_000_000}"
        exists = db.scalar(
            select(QQBindingSession.session_id).where(QQBindingSession.bind_code == candidate)
        )
        if not exists:
            bind_code = candidate
            break
    if not bind_code:
        raise RuntimeError("unable to allocate QQ binding code")

    session_id = secrets.token_hex(16)
    settings = get_settings()
    qrcode_url = ""
    qq_task_id = ""
    qq_key = ""
    bridge_session_id = ""

    try:
        from extensions.bots.qq_connector import QQConnectorClient

        connector = QQConnectorClient()
        conn_res = connector.start_bind_task()
        if conn_res and conn_res.get("qrcode_url"):
            qrcode_url = str(conn_res["qrcode_url"])
            qq_task_id = str(conn_res.get("task_id") or "")
            qq_key = str(conn_res.get("key") or "")
    except Exception as exc:
        logger.debug("QQ Connector not available: %s", exc)

    if not qrcode_url:
        try:
            from extensions.bots.qq_bot import QQBotClient

            bot_client = QQBotClient()
            bridge_res = bot_client.start_qr_session()
            if bridge_res and bridge_res.get("qrcode_url"):
                qrcode_url = str(bridge_res["qrcode_url"])
                bridge_session_id = str(bridge_res.get("session_id") or "")
        except Exception as exc:
            logger.debug("QQ bot bridge QR not available: %s", exc)

    if not qrcode_url and settings.qq_auth_enabled and settings.qq_app_id:
        from .auth import build_qq_auth_url

        qrcode_url = build_qq_auth_url(f"bind_{session_id}", settings)

    pending = QQBindingSession(
        session_id=session_id,
        user_id=user_id,
        bind_code=bind_code,
        qrcode_url=qrcode_url,
        qq_task_id=qq_task_id,
        qq_key=encrypt_secret(qq_key) if qq_key else "",
        bridge_session_id=bridge_session_id,
        status="WAITING",
        target_id="",
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(pending)
    db.commit()

    return {
        "session_id": session_id,
        "bind_code": bind_code,
        "qrcode_url": qrcode_url,
        "expires_in_seconds": 300,
        "instruction": "请使用手机 QQ 扫描二维码添加机器人并授权",
    }


def check_qq_binding_session(
    session_id: str,
    db: Session | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    if db is None:
        return {"status": "EXPIRED", "message": "绑定会话不存在或已失效"}

    session = db.get(QQBindingSession, session_id)
    if session is None or (user_id is not None and session.user_id != user_id):
        return {"status": "EXPIRED", "message": "绑定会话不存在或已失效"}

    if _ensure_utc(session.expires_at) <= utcnow():
        session.status = "EXPIRED"
        session.updated_at = utcnow()
        db.commit()
        return {"status": "EXPIRED", "message": "二维码已过期，请点击刷新"}

    if session.status == "BOUND":
        result = _session_status(session)
        result["message"] = "绑定成功"
        return result

    if session.qq_task_id and session.qq_key:
        try:
            from extensions.bots.qq_connector import QQConnectorClient

            connector = QQConnectorClient()
            res = connector.poll_bind_task(session.qq_task_id, decrypt_secret(session.qq_key))
            st = res.get("status")
            if st == "COMPLETED":
                app_id = str(res.get("app_id") or "")
                app_secret = str(res.get("app_secret") or "")
                user_openid = str(res.get("user_openid") or "")
                binding = complete_qq_binding(
                    db,
                    session_id,
                    target_id=user_openid,
                    bot_token=app_secret,
                    extra_meta={"app_id": app_id, "user_openid": user_openid},
                    channel="qq",
                )
                if binding is None:
                    return {
                        "status": "EXPIRED",
                        "message": "绑定校验失败或该 QQ 已绑定其他账号，请重新生成二维码",
                    }
                try:
                    from extensions.bots.qq_bot import QQBotClient

                    welcome_msg = (
                        "🎉 恭喜！您已成功连接 PriceMemo QQ 机器人好友。\n"
                        "💡 常用指令：\n"
                        "  • plus — 查询 ChatGPT Plus 最低价(库存充足)\n"
                        "  • pro — 查询 Claude Pro 最低价\n"
                        "  • 降价 — 查看今日降价精选\n"
                        "  • 关注 — 查看您在 PriceMemo 关注的全部商品及最新价格\n"
                        "  • 行情 — 查看全网大盘报价"
                    )
                    QQBotClient(app_id=app_id, app_secret=app_secret).send_c2c_message(
                        user_openid, welcome_msg, app_id=app_id, app_secret=app_secret
                    )
                except Exception as exc:
                    logger.warning("Failed sending QQ welcome message: %s", exc)
                refreshed = db.get(QQBindingSession, session_id)
                result = _session_status(refreshed or session)
                result["status"] = "BOUND"
                result["message"] = "绑定成功！已成功连接手机 QQ 机器人。"
                return result
            if st == "EXPIRED":
                session.status = "EXPIRED"
                session.updated_at = utcnow()
                db.commit()
                return {"status": "EXPIRED", "message": "二维码已过期，请重新生成"}
        except Exception as exc:
            logger.debug("Error querying QQ connector status: %s", exc)

    if session.bridge_session_id:
        try:
            from extensions.bots.qq_bot import QQBotClient

            bridge_status = QQBotClient().check_qr_session(session.bridge_session_id)
            if bridge_status:
                b_status = bridge_status.get("status")
                if b_status in ("COMPLETED", "BOUND"):
                    creds = bridge_status.get("credentials") or {}
                    target_id = str(creds.get("user_openid") or creds.get("app_id") or "qq_bound_user")
                    app_id = str(creds.get("app_id") or "")
                    app_secret = str(creds.get("app_secret") or "")
                    binding = complete_qq_binding(
                        db,
                        session_id,
                        target_id,
                        bot_token=app_secret,
                        extra_meta={"app_id": app_id, "user_openid": target_id},
                        channel="qq",
                    )
                    if binding is None:
                        return {
                            "status": "EXPIRED",
                            "message": "绑定校验失败或该 QQ 已绑定其他账号，请重新生成二维码",
                        }
                    refreshed = db.get(QQBindingSession, session_id)
                    result = _session_status(refreshed or session)
                    result["status"] = "BOUND"
                    result["message"] = "绑定成功"
                    return result
                if b_status == "EXPIRED":
                    session.status = "EXPIRED"
                    session.updated_at = utcnow()
                    db.commit()
                    return {"status": "EXPIRED", "message": "二维码已过期，请重新生成"}
        except Exception as exc:
            logger.debug("Error querying bridge QR status: %s", exc)

    return _session_status(session)


def bind_current_user_qq(db: Session, user: User) -> UserBotBinding | None:
    if not user.qq_openid:
        return None

    target_id = user.qq_openid.strip()
    _advisory_lock(db, "qq-target", target_id)
    collision = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == "qq",
            UserBotBinding.target_id == target_id,
            UserBotBinding.user_id != user.id,
        )
    )
    if collision is not None:
        db.rollback()
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
            target_id=target_id,
            is_active=True,
            notify_price_drop=True,
            notify_price_hike=True,
            created_at=now,
            updated_at=now,
        )
        db.add(binding)
    else:
        binding.target_id = target_id
        binding.is_active = True
        binding.updated_at = now
    try:
        db.commit()
        db.refresh(binding)
    except IntegrityError:
        db.rollback()
        return None
    return binding


def complete_qq_binding(
    db: Session,
    bind_code_or_session: str,
    target_id: str,
    bot_token: str = "",
    extra_meta: dict | None = None,
    channel: str = "qq",
    expected_user_id: int | None = None,
) -> UserBotBinding | None:
    target_id = (target_id or "").strip()
    if not target_id or not _allow_binding_attempt(db, target_id):
        logger.warning("QQ bind attempt rejected for target %s", target_id or "<empty>")
        return None

    pending = _find_pending_binding(db, bind_code_or_session)
    if pending is None:
        return None
    if expected_user_id is not None and pending.user_id != expected_user_id:
        return None
    if pending.status == "BOUND":
        if pending.target_id != target_id:
            return None
        return db.scalar(
            select(UserBotBinding).where(
                UserBotBinding.user_id == pending.user_id,
                UserBotBinding.channel == channel,
            )
        )
    if pending.status != "WAITING":
        return None

    now = utcnow()
    _advisory_lock(db, "qq-target", target_id)
    claimed = db.execute(
        update(QQBindingSession)
        .where(
            QQBindingSession.session_id == pending.session_id,
            QQBindingSession.status == "WAITING",
            QQBindingSession.expires_at > now,
        )
        .values(status="CLAIMING", updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if not claimed.rowcount:
        db.rollback()
        return None

    collision = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.channel == channel,
            UserBotBinding.target_id == target_id,
            UserBotBinding.user_id != pending.user_id,
        )
    )
    if collision is not None:
        db.execute(
            update(QQBindingSession)
            .where(QQBindingSession.session_id == pending.session_id)
            .values(status="WAITING", updated_at=utcnow())
        )
        db.commit()
        return None

    binding = db.scalar(
        select(UserBotBinding).where(
            UserBotBinding.user_id == pending.user_id,
            UserBotBinding.channel == channel,
        )
    )
    encrypted_token = encrypt_secret(bot_token) if bot_token else ""
    if binding is None:
        binding = UserBotBinding(
            user_id=pending.user_id,
            channel=channel,
            target_id=target_id,
            bot_token=encrypted_token,
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
        if encrypted_token:
            binding.bot_token = encrypted_token
        if extra_meta:
            binding.extra_meta = extra_meta
        binding.is_active = True
        binding.updated_at = now

    db.execute(
        update(QQBindingSession)
        .where(QQBindingSession.session_id == pending.session_id)
        .values(status="BOUND", target_id=target_id, updated_at=now)
    )
    try:
        db.commit()
        db.refresh(binding)
    except IntegrityError:
        db.rollback()
        return None
    except Exception:
        db.rollback()
        raise
    logger.info("Successfully bound user %d to %s target %s", pending.user_id, channel, target_id)
    return binding


def unbind_user_channel(db: Session, user_id: int, channel: str = "qq") -> bool:
    db.execute(delete(QQBindingSession).where(QQBindingSession.user_id == user_id))
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
