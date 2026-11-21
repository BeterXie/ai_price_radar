"""QQ group opt-in, native permission events, and one digest per publication."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import String, and_, case, cast, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import CatalogSnapshot, QQGroupSubscription, SystemSetting, UserBotBinding
from app.services.credential_crypto import decrypt_secret
from .formatter import format_detection_time, render_qq_group_digest
from .qq_bot import QQBotClient
from .qq_text import normalize_qq_text

logger = logging.getLogger(__name__)
GROUP_EVENTS = {"GROUP_ADD_ROBOT", "GROUP_DEL_ROBOT", "GROUP_MSG_RECEIVE", "GROUP_MSG_REJECT"}
GROUP_COMMANDS = {"开启群推送", "关闭群推送", "群推送状态", "群推送"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def active_bot_credentials(db, only_app_id: str | None = None) -> dict[str, str]:
    found = {}
    query = select(UserBotBinding).where(UserBotBinding.channel == "qq", UserBotBinding.is_active.is_(True))
    if only_app_id:
        query = query.where(cast(UserBotBinding.extra_meta["app_id"].as_string(), String) == only_app_id)
    for binding in db.scalars(query):
        app_id = (binding.extra_meta or {}).get("app_id")
        secret = decrypt_secret(binding.bot_token)
        if app_id and secret:
            found[str(app_id).strip()] = secret.strip()
    app_id, secret = os.getenv("QQ_BOT_APP_ID", "").strip(), os.getenv("QQ_BOT_APP_SECRET", "").strip()
    if app_id and secret:
        found.setdefault(app_id, secret)
    return found


def _get_group(db, app_id: str, group_openid: str) -> QQGroupSubscription:
    query = select(QQGroupSubscription).where(QQGroupSubscription.app_id == app_id,
                                             QQGroupSubscription.group_openid == group_openid)
    row = db.scalar(query)
    if row is None:
        try:
            with db.begin_nested():
                row = QQGroupSubscription(app_id=app_id, group_openid=group_openid)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.scalar(query)
            if row is None:
                raise
    return row


def apply_group_event(app_id: str, event: str, data: dict) -> None:
    """Only authenticated gateway lifecycle events can set native permission."""
    group = data.get("group_openid")
    if event not in GROUP_EVENTS or not isinstance(group, str) or not group or len(group) > 128:
        return
    try:
        happened = datetime.fromtimestamp(int(data["timestamp"]), timezone.utc)
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        logger.warning("QQ group event missing a valid timestamp [event=%s]", event)
        return
    with SessionLocal() as db:
        row = _get_group(db, app_id, group)
        values = {"permission_event_at": happened, "permission_event_kind": event, "updated_at": utcnow(),
                  "permission_version": QQGroupSubscription.permission_version + 1,
                  "state_version": QQGroupSubscription.state_version + 1}
        if event == "GROUP_ADD_ROBOT":
            values.update(is_member=True,
                          allow_proactive=case((QQGroupSubscription.allow_proactive.is_(False), False), else_=None))
        elif event == "GROUP_DEL_ROBOT":
            values.update(is_member=False, allow_proactive=False)
        elif event == "GROUP_MSG_REJECT":
            values.update(allow_proactive=False)
        else:
            values.update(is_member=True, allow_proactive=True, last_error_code=None)
        # Native permission and local subscription have independent clocks.
        # A newer local opt-out must not discard an older native denial.
        db.execute(update(QQGroupSubscription).where(
            QQGroupSubscription.id == row.id,
            _event_order(QQGroupSubscription.permission_event_at, QQGroupSubscription.permission_event_kind, event, happened),
        ).values(**values).execution_options(synchronize_session=False))
        db.execute(update(QQGroupSubscription).where(
            QQGroupSubscription.id == row.id,
            _event_order(QQGroupSubscription.last_event_at, QQGroupSubscription.last_event_kind, event, happened),
        ).values(subscribed=event == "GROUP_MSG_RECEIVE", last_event_at=happened, last_event_kind=event,
                 state_version=QQGroupSubscription.state_version + 1).execution_options(synchronize_session=False))
        db.commit()


def _event_order(at_column, kind_column, event, happened):
    ordering = at_column < happened
    if event in {"GROUP_MSG_RECEIVE", "command_enable"}:
        allowed_kinds = ["GROUP_ADD_ROBOT", "state_query"] if event == "GROUP_MSG_RECEIVE" else ["GROUP_ADD_ROBOT"]
        ordering = or_(ordering, and_(at_column == happened, kind_column.in_(allowed_kinds)))
    elif event in {"GROUP_MSG_REJECT", "GROUP_DEL_ROBOT"}:
        ordering = at_column <= happened
    return or_(at_column.is_(None), ordering)


def group_command(text: str) -> str:
    clean = normalize_qq_text(text).lstrip("/")
    return clean if clean in GROUP_COMMANDS else ""


def handle_group_command(text: str, *, app_id: str, app_secret: str, group_openid: str,
                         member_role: str, message_timestamp: str = "") -> str | None:
    command = group_command(text)
    if not command:
        return None
    if command in {"开启群推送", "关闭群推送"} and member_role not in {"owner", "admin"}:
        return "只有群主或管理员可以开启或关闭群推送。可发送「群推送状态」查看当前状态。"
    state = None
    happened = None
    query_started_at = utcnow()
    if command in {"开启群推送", "关闭群推送"}:
        try:
            happened = datetime.fromisoformat(message_timestamp.replace("Z", "+00:00"))
            if happened.tzinfo is None:
                raise ValueError("missing message timezone")
            happened = happened.astimezone(timezone.utc).replace(microsecond=0)
        except (ValueError, TypeError, AttributeError):
            return "无法确认这条命令的发送时间，请群管理员重新发送。"
    if command == "开启群推送":
        state = QQBotClient(app_id=app_id, app_secret=app_secret).get_group_state(group_openid)
    with SessionLocal() as db:
        row = _get_group(db, app_id, group_openid)
        if happened is not None:
            enabling = command == "开启群推送"
            values = {"subscribed": enabling, "last_event_at": happened,
                      "last_event_kind": "command_enable" if enabling else "command_disable",
                      "state_version": QQGroupSubscription.state_version + 1, "updated_at": utcnow()}
            if enabling:
                values.update(last_error_code=None)
            ordering = _event_order(QQGroupSubscription.last_event_at, QQGroupSubscription.last_event_kind,
                                    "command_enable" if enabling else "GROUP_MSG_REJECT", happened)
            changed = db.execute(update(QQGroupSubscription).where(
                QQGroupSubscription.id == row.id,
                ordering,
            ).values(**values).execution_options(synchronize_session=False))
            if changed.rowcount and enabling and state is not None:
                db.execute(update(QQGroupSubscription).where(
                    QQGroupSubscription.id == row.id,
                    or_(QQGroupSubscription.permission_event_at.is_(None),
                        QQGroupSubscription.permission_event_at < query_started_at.replace(microsecond=0)),
                ).values(is_member=True, allow_proactive=state["allow_proactive_msg"],
                         permission_event_at=query_started_at.replace(microsecond=0), permission_event_kind="state_query",
                         permission_version=QQGroupSubscription.permission_version + 1,
                         state_version=QQGroupSubscription.state_version + 1).execution_options(synchronize_session=False))
            db.commit()
            db.refresh(row)
            if not changed.rowcount:
                return "本群已有更新的推送设置，这条重复或较早的命令未执行。请发送「群推送状态」查看。"
        else:
            db.commit()
        if not row.subscribed:
            lines = ["本群推送已关闭。群主或管理员可发送「开启群推送」订阅降价、涨价和 Team 车提醒。"]
        elif row.allow_proactive is False or not row.is_member:
            lines = ["已记录群订阅，但 QQ 主动消息权限未开启。请群管理员到机器人资料页开启通知，之后会自动恢复推送。"]
        else:
            lines = ["本群已订阅降价、涨价和 Team 车提醒。每次报价更新最多发送一条摘要，完整榜单链接始终展示最新一期。"]
        if row.subscribed and row.allow_proactive is None:
            lines.append("QQ 未返回可查询的主动消息权限；实际发送仍由群内通知开关控制。")
        if row.last_error_code:
            retry = "下一次更新时重试。" if row.subscribed and row.is_member and row.allow_proactive is not False else "恢复订阅和 QQ 权限后再发送。"
            lines.append(f"上次发送未成功（错误码 {row.last_error_code}），{retry}")
        if row.last_sent_at:
            lines.append(f"上次成功推送：{format_detection_time(row.last_sent_at)}")
        lines.append("停止提醒：群主或管理员发送「关闭群推送」，或在 QQ 机器人资料页关闭通知。")
        return "\n".join(lines)


def dispatch_group_alerts(events, team_offers, *, db, snapshot_id: int | None,
                          detected_at: datetime | None, site_url: str, stale_offer_hours: int | None = None) -> None:
    if snapshot_id is None:
        return
    credentials = active_bot_credentials(db)
    groups = list(db.scalars(select(QQGroupSubscription).where(
        QQGroupSubscription.subscribed.is_(True), QQGroupSubscription.is_member.is_(True),
        or_(QQGroupSubscription.allow_proactive.is_(None), QQGroupSubscription.allow_proactive.is_(True)),
        or_(QQGroupSubscription.last_snapshot_id.is_(None), QQGroupSubscription.last_snapshot_id < snapshot_id),
    ).order_by(QQGroupSubscription.id)))
    clients = {}
    client_secrets = {}
    rate_limited_apps = set()
    for group in groups:
        secret = credentials.get(group.app_id)
        if not secret or group.app_id in rate_limited_apps:
            continue
        # Respect both the stricter unverified-bot limit (30/min) and each
        # group's 20/min limit, including back-to-back importer processes.
        last_bot_attempt = db.scalar(select(func.max(QQGroupSubscription.last_attempt_at)).where(QQGroupSubscription.app_id == group.app_id))
        now = utcnow()
        delays = [0.0]
        if last_bot_attempt:
            delays.append(2.1 - (now - _aware(last_bot_attempt)).total_seconds())
        if group.last_attempt_at:
            delays.append(3.1 - (now - _aware(group.last_attempt_at)).total_seconds())
        if max(delays) > 0:
            time.sleep(min(max(delays), 3.1))
        secret = active_bot_credentials(db, group.app_id).get(group.app_id)
        if not secret:
            continue
        if client_secrets.get(group.app_id) != secret:
            clients[group.app_id] = QQBotClient(app_id=group.app_id, app_secret=secret)
            client_secrets[group.app_id] = secret
        client = clients[group.app_id]
        if not client.prepare_send(group=True):
            continue
        now = utcnow()
        db.refresh(group)
        enabled = db.scalar(select(SystemSetting.value).where(SystemSetting.key == "bot_enabled"))
        if enabled and enabled.strip().lower() not in {"true", "1", "yes", "on"}:
            break
        current_id = db.scalar(select(CatalogSnapshot.id).where(CatalogSnapshot.published_at.is_not(None))
                               .order_by(CatalogSnapshot.id.desc()).limit(1))
        if current_id != snapshot_id:
            break
        from .formatter import fresh_alert_item
        current_team = [offer for offer in team_offers if offer.ends_at is not None and _aware(offer.ends_at) > now
                        and fresh_alert_item(offer, now, stale_offer_hours)]
        current_events = [event for event in events if fresh_alert_item(event, now, stale_offer_hours)]
        if not current_events and not current_team:
            continue
        if not group.subscribed or not group.is_member or group.allow_proactive is False:
            continue
        message = render_qq_group_digest(current_events, current_team, detected_at=detected_at, site_base_url=site_url)
        claimed_version = group.state_version
        claimed_permission_version = group.permission_version
        # Claim before HTTP: an uncertain network outcome must never replay a
        # digest. Failures retry with the next publication, not the same one.
        claim = db.execute(update(QQGroupSubscription).where(
            QQGroupSubscription.id == group.id, QQGroupSubscription.subscribed.is_(True),
            QQGroupSubscription.state_version == claimed_version,
            QQGroupSubscription.is_member.is_(True),
            or_(QQGroupSubscription.allow_proactive.is_(None), QQGroupSubscription.allow_proactive.is_(True)),
            or_(QQGroupSubscription.last_snapshot_id.is_(None), QQGroupSubscription.last_snapshot_id < snapshot_id),
        ).values(last_snapshot_id=snapshot_id, last_attempt_at=now))
        db.commit()
        if not claim.rowcount:
            continue
        ok = client.send_group_message(group.group_openid, message)
        code = client.last_group_error_code
        result = {"last_error_code": None if ok else code or -1}
        permission_result = {}
        if ok:
            result["last_sent_at"] = utcnow()
        elif code in {40034101, 40054003}:
            permission_result.update(is_member=False, subscribed=False, allow_proactive=False,
                                     last_event_at=utcnow().replace(microsecond=0), last_event_kind="send_denied")
        elif code == 40034105:
            permission_result["allow_proactive"] = False
        elif code == 40034100 or code == 429:
            rate_limited_apps.add(group.app_id)
        db.execute(update(QQGroupSubscription).where(QQGroupSubscription.id == group.id,
                   QQGroupSubscription.last_snapshot_id == snapshot_id).values(**result))
        if permission_result:
            permission_result.update(permission_event_at=utcnow().replace(microsecond=0), permission_event_kind="send_denied",
                                     permission_version=QQGroupSubscription.permission_version + 1,
                                     state_version=QQGroupSubscription.state_version + 1)
            db.execute(update(QQGroupSubscription).where(QQGroupSubscription.id == group.id,
                       QQGroupSubscription.last_snapshot_id == snapshot_id,
                       QQGroupSubscription.permission_version == claimed_permission_version).values(**permission_result))
        db.commit()
        logger.info("QQ group digest [subscription=%s, snapshot=%s, success=%s, code=%s]", group.id, snapshot_id, ok, code)
