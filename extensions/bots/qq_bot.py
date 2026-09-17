from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class QQBotClient:
    """Tencent QQ Bot client for user notifications.

    Supports both:
    1. Direct Tencent Official Open API (OAuth AppAccessToken + sgroup API).
    2. Local QQ Bot Bridge (compatible with Node bridge from Dota AI Decision Lab).
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_secret: str | None = None,
        bridge_url: str | None = None,
        bridge_token: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.app_id = (app_id or os.getenv("QQ_BOT_APP_ID", "")).strip()
        self.app_secret = (app_secret or os.getenv("QQ_BOT_APP_SECRET", "")).strip()
        self.bridge_url = (bridge_url or os.getenv("QQ_BOT_BRIDGE_URL", "")).rstrip("/")
        self.bridge_token = (bridge_token or os.getenv("QQ_BOT_BRIDGE_TOKEN", "")).strip()
        self.timeout_seconds = timeout_seconds

        self._token_cache: dict[str, tuple[str, float]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.bridge_url or (self.app_id and self.app_secret))

    def _get_access_token(self, app_id: str | None = None, app_secret: str | None = None) -> str | None:
        """Fetch and cache QQ Bot access token from Tencent."""
        target_app_id = (app_id or self.app_id).strip()
        target_secret = (app_secret or self.app_secret).strip()
        if not target_app_id or not target_secret:
            return None

        cache_key = f"{target_app_id}:{target_secret}"
        now = time.time()
        cached = self._token_cache.get(cache_key)
        if cached and now < (cached[1] - 60):
            return cached[0]

        url = "https://bots.qq.com/app/getAppAccessToken"
        payload = {"appId": target_app_id, "clientSecret": target_secret}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token")
                    expires_in = int(data.get("expires_in") or 7200)
                    if token:
                        self._token_cache[cache_key] = (token, now + expires_in)
                        return token
                logger.error("Failed to get QQ Bot access token for %s: %d %s", target_app_id, resp.status_code, resp.text)
                return None
        except Exception as exc:
            logger.error("Error fetching QQ Bot access token for %s: %s", target_app_id, exc)
            return None

    def send_c2c_message(
        self,
        target_openid: str,
        text: str,
        app_id: str | None = None,
        app_secret: str | None = None,
        msg_id: str | None = None,
    ) -> bool:
        """Send message to a bound QQ user."""
        if not target_openid.strip():
            return False

        # Mode A: Via Node bridge if bridge_url is set
        if self.bridge_url:
            return self._send_via_bridge(target_openid, text, account_id=app_id)

        # Mode B: Direct Open API
        effective_app_id = (app_id or self.app_id).strip()
        token = self._get_access_token(effective_app_id, app_secret)
        if not token:
            logger.warning("QQ Bot credentials missing or token fetch failed for app_id: %s", effective_app_id)
            return False

        url = f"https://api.sgroup.qq.com/v2/users/{target_openid}/messages"
        headers = {
            "Authorization": f"QQBot {token}",
            "X-Union-Appid": effective_app_id,
        }
        payload: dict[str, Any] = {
            "content": text,
            "msg_type": 0,
        }
        if msg_id:
            payload["msg_id"] = msg_id
            payload["msg_seq"] = int(time.time() * 1000) % 65535 + 1

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    logger.info("Delivered QQ notification to openid: %s", target_openid[:6] + "...")
                    return True
                logger.error("QQ Open API error %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Failed to send QQ notification: %s", exc)
            return False

    def send_group_message(
        self,
        group_openid: str,
        text: str,
        app_id: str | None = None,
        app_secret: str | None = None,
        msg_id: str | None = None,
    ) -> bool:
        """Send passive or active reply to a QQ group."""
        if not group_openid.strip():
            return False

        effective_app_id = (app_id or self.app_id).strip()
        token = self._get_access_token(effective_app_id, app_secret)
        if not token:
            logger.warning("QQ Bot credentials missing or token fetch failed for app_id: %s", effective_app_id)
            return False

        url = f"https://api.sgroup.qq.com/v2/groups/{group_openid}/messages"
        headers = {
            "Authorization": f"QQBot {token}",
            "X-Union-Appid": effective_app_id,
        }
        payload: dict[str, Any] = {
            "content": text,
            "msg_type": 0,
        }
        if msg_id:
            payload["msg_id"] = msg_id
            payload["msg_seq"] = int(time.time() * 1000) % 65535 + 1

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    logger.info("Delivered QQ group message to: %s", group_openid[:6] + "...")
                    return True
                logger.error("QQ Group Open API error %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Failed to send QQ group message: %s", exc)
            return False


    def _send_via_bridge(self, target_openid: str, text: str, account_id: str | None = None) -> bool:
        """Dispatch via local bridge HTTP endpoint."""
        url = f"{self.bridge_url}/send"
        headers = {}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"
        payload: dict[str, Any] = {
            "scope": "c2c",
            "target_id": target_openid,
            "text": text,
        }
        if account_id:
            payload["account_id"] = account_id
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return True
                logger.error("QQ bridge error %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Failed to send via QQ bridge: %s", exc)
            return False

    def start_qr_session(self) -> dict[str, Any] | None:
        """Start a QR login/binding session via bridge connector."""
        if not self.bridge_url:
            return None
        url = f"{self.bridge_url}/qr/start"
        headers = {}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("QQ bridge /qr/start failed %d: %s", resp.status_code, resp.text)
                return None
        except Exception as exc:
            logger.debug("QQ bridge /qr/start unreachable: %s", exc)
            return None

    def check_qr_session(self, session_id: str) -> dict[str, Any] | None:
        """Check status of QR session on bridge connector."""
        if not self.bridge_url:
            return None
        url = f"{self.bridge_url}/qr/status"
        headers = {}
        if self.bridge_token:
            headers["Authorization"] = f"Bearer {self.bridge_token}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url, params={"session_id": session_id}, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as exc:
            logger.debug("QQ bridge /qr/status unreachable: %s", exc)
            return None

    def handle_incoming_message(self, sender_id: str, text: str, db_session: Any = None) -> str:
        """Process inbound chat command, query lowest price or setting, and reply."""
        from .chat_commands import handle_chat_command

        reply = handle_chat_command(text, sender_id=sender_id, channel="qq", db=db_session)
        if sender_id and self.is_configured:
            try:
                self.send_c2c_message(sender_id, reply)
            except Exception as exc:
                logger.error("Failed sending reply to QQ user %s: %s", sender_id, exc)
        return reply
