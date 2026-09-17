"""Official Tencent QQ Bot WebSocket Gateway Service.

Maintains persistent WebSocket connection to Tencent QQ Bot Gateway (wss://api.sgroup.qq.com/websocket),
listens for real-time C2C_MESSAGE_CREATE and FRIEND_ADD events, routes user commands through
handle_chat_command, and sends instant passive replies back to the user on QQ.

Zero external Node.js required — runs natively in Python via `websockets`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from sqlalchemy import select
import websockets

from app.database import SessionLocal
from app.models import SystemSetting, UserBotBinding
from .chat_commands import handle_chat_command
from .qq_bot import QQBotClient

logger = logging.getLogger(__name__)

QQ_GATEWAY_URL = "wss://api.sgroup.qq.com/websocket"
INTENTS_GROUP_AND_C2C = 1 << 25  # 33554432


def _is_bot_enabled() -> bool:
    """Check if global bot service is enabled by admin."""
    try:
        with SessionLocal() as db:
            s = db.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled"))
            if not s or not s.value:
                return True
            return s.value.strip().lower() in ("true", "1", "yes", "on")
    except Exception as e:
        logger.warning("Failed checking bot_enabled setting: %s", e)
        return True


class QQGatewayService:
    """Manages WebSocket Gateway lifecycle for all active bound QQ Bots."""

    def __init__(self) -> None:
        self.running = False
        self.bot_client = QQBotClient()
        self._monitor_task: asyncio.Task | None = None
        self._bot_tasks: dict[str, asyncio.Task] = {}

    def start(self) -> None:
        """Start the gateway monitor in background asyncio loop."""
        if self.running:
            return
        self.running = True
        loop = asyncio.get_event_loop()
        self._monitor_task = loop.create_task(self._monitor_loop())
        print(">>> [QQBotGateway] Service monitor task started <<<", flush=True)
        logger.info("QQGatewayService started.")

    async def stop(self) -> None:
        """Gracefully stop all gateway connections."""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        for app_id, task in list(self._bot_tasks.items()):
            task.cancel()
        self._bot_tasks.clear()
        print(">>> [QQBotGateway] Service stopped <<<", flush=True)
        logger.info("QQGatewayService stopped.")

    async def _monitor_loop(self) -> None:
        """Periodically scan active QQ bots and maintain their connection tasks."""
        while self.running:
            try:
                bot_enabled = _is_bot_enabled()
                if not bot_enabled:
                    # Cancel any active connections when bot is turned off
                    for app_id, task in list(self._bot_tasks.items()):
                        task.cancel()
                    self._bot_tasks.clear()
                    await asyncio.sleep(15.0)
                    continue

                # Query distinct active (app_id, bot_token)
                active_bots: dict[str, str] = {}
                try:
                    with SessionLocal() as db:
                        bindings = db.scalars(
                            select(UserBotBinding).where(
                                UserBotBinding.channel == "qq",
                                UserBotBinding.is_active == True,
                            )
                        ).all()
                        for b in bindings:
                            app_id = (b.extra_meta or {}).get("app_id") if b.extra_meta else None
                            app_secret = b.bot_token
                            if app_id and app_secret:
                                active_bots[str(app_id).strip()] = str(app_secret).strip()
                except Exception as db_err:
                    logger.error("Error querying active QQ bot bindings: %s", db_err)

                # Fallback to env vars if present
                env_app_id = os.getenv("QQ_BOT_APP_ID", "").strip()
                env_app_secret = os.getenv("QQ_BOT_APP_SECRET", "").strip()
                if env_app_id and env_app_secret and env_app_id not in active_bots:
                    active_bots[env_app_id] = env_app_secret

                # Launch tasks for newly discovered or disconnected bots
                current_app_ids = set(active_bots.keys())
                for app_id, secret in active_bots.items():
                    existing_task = self._bot_tasks.get(app_id)
                    if existing_task is None or existing_task.done():
                        logger.info("Launching QQ Bot Gateway task for app_id: %s", app_id)
                        self._bot_tasks[app_id] = asyncio.create_task(
                            self._run_bot_gateway(app_id, secret)
                        )

                # Cancel tasks for removed bots
                for app_id in list(self._bot_tasks.keys()):
                    if app_id not in current_app_ids:
                        logger.info("Cancelling QQ Bot Gateway task for removed app_id: %s", app_id)
                        self._bot_tasks[app_id].cancel()
                        del self._bot_tasks[app_id]

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unexpected error in QQ gateway monitor loop: %s", exc)

            await asyncio.sleep(15.0)

    async def _run_bot_gateway(self, app_id: str, app_secret: str) -> None:
        """Run single bot WebSocket gateway lifecycle with reconnect & backoff."""
        session_id: str | None = None
        last_seq: int | None = None
        backoff = 1.0

        while self.running:
            ws = None
            heartbeat_task = None
            try:
                # 1. Fetch access token
                token = self.bot_client._get_access_token(app_id, app_secret)
                if not token:
                    logger.warning("Cannot get token for QQ bot %s, retrying in %.1fs...", app_id, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 30.0)
                    continue

                print(f">>> [QQBotGateway] Connecting [{app_id}] -> {QQ_GATEWAY_URL} <<<", flush=True)
                logger.info("Connecting QQ Bot Gateway [%s] -> %s", app_id, QQ_GATEWAY_URL)
                ws = await websockets.connect(
                    QQ_GATEWAY_URL,
                    ping_interval=None,  # Protocol handles application-level heartbeat
                    close_timeout=10.0,
                )

                # 2. Wait for HELLO (op 10)
                hello_raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                hello_payload = json.loads(hello_raw)
                if hello_payload.get("op") != 10:
                    logger.warning("Expected HELLO (op 10), got: %s", hello_payload)
                    await ws.close()
                    continue

                interval_ms = hello_payload.get("d", {}).get("heartbeat_interval", 45000)
                interval_sec = max(interval_ms / 1000.0, 5.0)

                # 3. Start Heartbeat background task
                async def _heartbeat_loop(ws_conn: websockets.ClientConnection):
                    try:
                        while True:
                            await asyncio.sleep(interval_sec * 0.9)
                            hb_msg = json.dumps({"op": 1, "d": last_seq})
                            await ws_conn.send(hb_msg)
                    except asyncio.CancelledError:
                        pass
                    except Exception as hb_err:
                        logger.debug("Heartbeat error [%s]: %s", app_id, hb_err)

                heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))

                # 4. IDENTIFY or RESUME
                if session_id and last_seq is not None:
                    resume_payload = {
                        "op": 6,
                        "d": {
                            "token": f"QQBot {token}",
                            "session_id": session_id,
                            "seq": last_seq,
                        },
                    }
                    await ws.send(json.dumps(resume_payload))
                    logger.info("Sent RESUME for QQ bot [%s] (session_id=%s, seq=%s)", app_id, session_id, last_seq)
                else:
                    identify_payload = {
                        "op": 2,
                        "d": {
                            "token": f"QQBot {token}",
                            "intents": INTENTS_GROUP_AND_C2C,
                            "shard": [0, 1],
                        },
                    }
                    await ws.send(json.dumps(identify_payload))
                    logger.info("Sent IDENTIFY for QQ bot [%s]", app_id)

                backoff = 1.0  # Reset backoff on successful handshake

                # 5. Event processing loop
                while self.running:
                    raw_msg = await ws.recv()
                    payload = json.loads(raw_msg)
                    op = payload.get("op")
                    s = payload.get("s")
                    t = payload.get("t")
                    d = payload.get("d") or {}

                    if s is not None:
                        last_seq = s

                    if op == 0:  # DISPATCH
                        if t == "READY":
                            session_id = d.get("session_id")
                            user_info = d.get("user", {})
                            bot_name = user_info.get("username", "PriceMemo Bot")
                            print(f">>> [QQBotGateway] READY! app_id={app_id}, bot_name='{bot_name}' <<<", flush=True)
                            logger.info("✅ QQ Bot [%s - %s] ONLINE and READY!", app_id, bot_name)

                        elif t == "RESUMED":
                            print(f">>> [QQBotGateway] RESUMED! app_id={app_id} <<<", flush=True)
                            logger.info("✅ QQ Bot [%s] session RESUMED successfully.", app_id)

                        elif t == "C2C_MESSAGE_CREATE":
                            # Inbound private message from a QQ user
                            msg_id = d.get("id")
                            raw_content = str(d.get("content", "")).strip()
                            author = d.get("author", {})
                            user_openid = author.get("user_openid") or author.get("id")

                            if user_openid and raw_content:
                                print(f">>> [QQBotGateway] Inbound message: '{raw_content}' from {user_openid} <<<", flush=True)
                                logger.info("Received QQ C2C message [%s]: '%s'", user_openid[:6] + "...", raw_content[:20])
                                # Execute command router
                                reply_text = handle_chat_command(
                                    raw_text=raw_content,
                                    sender_id=user_openid,
                                    channel="qq",
                                )
                                # Passive reply back
                                ok = self.bot_client.send_c2c_message(
                                    target_openid=user_openid,
                                    text=reply_text,
                                    app_id=app_id,
                                    app_secret=app_secret,
                                    msg_id=msg_id,
                                )
                                print(f">>> [QQBotGateway] Passive reply sent (success={ok}): '{reply_text[:30]}...' <<<", flush=True)

                        elif t in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
                            # Inbound group message (@机器人 in QQ group)
                            msg_id = d.get("id")
                            raw_content = str(d.get("content", "")).strip()
                            group_openid = d.get("group_openid")
                            author = d.get("author", {})
                            member_openid = author.get("member_openid") or author.get("id")

                            # Clean @bot mention prefix (<@!xxx> or @xxx)
                            cleaned_content = re.sub(r"^<@!\d+>\s*", "", raw_content)
                            cleaned_content = re.sub(r"^@[^\s]+\s*", "", cleaned_content).strip()
                            if not cleaned_content:
                                cleaned_content = "帮助"

                            if group_openid:
                                print(f">>> [QQBotGateway] Group message in {group_openid[:6]}... by {member_openid[:6] if member_openid else 'unknown'}...: '{cleaned_content}' <<<", flush=True)
                                logger.info("Received QQ Group message [%s]: '%s'", group_openid[:6] + "...", cleaned_content[:20])
                                reply_text = handle_chat_command(
                                    raw_text=cleaned_content,
                                    sender_id=member_openid or "",
                                    channel="qq",
                                )
                                ok = self.bot_client.send_group_message(
                                    group_openid=group_openid,
                                    text=reply_text,
                                    app_id=app_id,
                                    app_secret=app_secret,
                                    msg_id=msg_id,
                                )
                                print(f">>> [QQBotGateway] Group reply sent (success={ok}) <<<", flush=True)

                        elif t == "FRIEND_ADD":
                            # User added robot as friend
                            user_openid = d.get("openid") or d.get("user_openid") or d.get("id")
                            if user_openid:
                                logger.info("QQ FRIEND_ADD event from: %s", user_openid[:6] + "...")
                                welcome_text = (
                                    "🎉 欢迎添加 PriceMemo 比价助手！\n"
                                    "------------------------------------\n"
                                    "您可以在这里直接向我发送指令查询主流 AI 模型/服务的全网最低价：\n"
                                    "• plus — 查询 ChatGPT Plus 最低价\n"
                                    "• pro — 查询 Claude Pro 最低价\n"
                                    "• gemini — 查询 Gemini Advanced 最低价\n"
                                    "• 行情 — 查看全网主流 AI 报价概况\n"
                                    "• 降价 — 查看最新降价与优惠\n"
                                    "• 关注 — 查看我关注的商品及目标价\n"
                                    "• 帮助 — 查看所有支持的指令\n"
                                    "------------------------------------\n"
                                    "🌐 官网: https://ai.pricememo.cn"
                                )
                                self.bot_client.send_c2c_message(
                                    target_openid=user_openid,
                                    text=welcome_text,
                                    app_id=app_id,
                                    app_secret=app_secret,
                                )

                    elif op == 11:  # HEARTBEAT_ACK
                        pass

                    elif op == 7:  # RECONNECT
                        logger.info("QQ Gateway requested RECONNECT for [%s]", app_id)
                        break

                    elif op == 9:  # INVALID_SESSION
                        logger.warning("QQ Gateway INVALID_SESSION for [%s], will re-identify", app_id)
                        session_id = None
                        last_seq = None
                        await asyncio.sleep(2.0)
                        break

            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed as cc:
                logger.info("QQ Gateway connection closed [%s]: code=%d, reason=%s", app_id, cc.code, cc.reason)
            except Exception as exc:
                logger.error("QQ Gateway exception [%s]: %s", app_id, exc)
            finally:
                if heartbeat_task:
                    heartbeat_task.cancel()
                if ws:
                    try:
                        await ws.close()
                    except Exception:
                        pass

            # Exponential backoff before reconnecting
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)


# Global singleton instance
qq_gateway_service = QQGatewayService()
