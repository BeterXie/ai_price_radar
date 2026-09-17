"""Tencent iLink ClawBot Client for PriceMemo.

Implements the official Tencent iLink Bot protocol (bot_type=3),
identical to Dota AI Decision Lab's wechat_clawbot provider:
- Direct QR code login with zero application needed on Tencent open platforms.
- Scanning QR code directly adds the robot as a WeChat/QQ contact friend.
- Bidirectional messaging via Tencent iLink HTTP API.
"""

from __future__ import annotations

import base64
import logging
import secrets
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

WECHAT_BOT_TYPE = "3"
WECHAT_BASE_URL = "https://ilinkai.weixin.qq.com"
WECHAT_APP_ID = "bot"
WECHAT_CHANNEL_VERSION = "2.4.6"
CLIENT_VERSION = "132102"
DEFAULT_BOT_AGENT = "PriceMemo/3.7.75"


def _random_wechat_uin() -> str:
    value = secrets.randbits(32)
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


class ClawBotClient:
    """Client for Tencent iLink ClawBot HTTP protocol."""

    def __init__(
        self,
        base_url: str = WECHAT_BASE_URL,
        bot_agent: str = DEFAULT_BOT_AGENT,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bot_agent = bot_agent
        self.timeout_seconds = timeout_seconds

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": _random_wechat_uin(),
            "iLink-App-Id": WECHAT_APP_ID,
            "iLink-App-ClientVersion": CLIENT_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _base_info(self) -> dict[str, str]:
        return {
            "channel_version": WECHAT_CHANNEL_VERSION,
            "bot_agent": self.bot_agent,
        }

    def start_qr_login(self) -> dict[str, Any]:
        """Request a real bot QR code from Tencent iLink.

        Returns:
            {"qrcode": "...", "qrcode_url": "https://liteapp.weixin.qq.com/q/..."}
        """
        url = f"{self.base_url}/ilink/bot/get_bot_qrcode?bot_type={WECHAT_BOT_TYPE}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json={"local_token_list": []}, headers=self._headers())
                if resp.status_code != 200:
                    logger.error("Tencent iLink get_bot_qrcode failed: %d %s", resp.status_code, resp.text)
                    return {"qrcode": "", "qrcode_url": ""}
                data = resp.json()
                qrcode = str(data.get("qrcode") or "")
                qrcode_url = str(data.get("qrcode_img_content") or "")
                return {"qrcode": qrcode, "qrcode_url": qrcode_url}
        except Exception as exc:
            logger.error("Exception in Tencent iLink get_bot_qrcode: %s", exc)
            return {"qrcode": "", "qrcode_url": ""}

    def poll_qr_status(self, qrcode: str, base_url: str | None = None) -> dict[str, Any]:
        """Poll the scan and authorization status of a QR code.

        Returns:
            {
                "status": "wait" | "scaned" | "confirmed" | "expired",
                "bot_token": str | None,
                "account_id": str | None,
                "user_id": str | None,
                "base_url": str | None,
            }
        """
        req_base = (base_url or self.base_url).rstrip("/")
        url = f"{req_base}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url, headers=self._headers())
                if resp.status_code != 200:
                    logger.error("Tencent iLink get_qrcode_status failed: %d %s", resp.status_code, resp.text)
                    return {"status": "failed", "message": f"HTTP {resp.status_code}"}
                data = resp.json()
                status = str(data.get("status") or "wait")
                return {
                    "status": status,
                    "bot_token": data.get("bot_token"),
                    "account_id": data.get("ilink_bot_id"),
                    "user_id": data.get("ilink_user_id"),
                    "base_url": data.get("baseurl"),
                    "redirect_host": data.get("redirect_host"),
                }
        except Exception as exc:
            logger.error("Exception in Tencent iLink get_qrcode_status: %s", exc)
            return {"status": "failed", "message": str(exc)}

    def notify_start(self, token: str, base_url: str | None = None) -> bool:
        """Call notifystart after confirmed to initialize bot session."""
        req_base = (base_url or self.base_url).rstrip("/")
        url = f"{req_base}/ilink/bot/msg/notifystart"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    url,
                    json={"base_info": self._base_info()},
                    headers=self._headers(token),
                )
                return resp.status_code == 200 and resp.json().get("ret") == 0
        except Exception as exc:
            logger.error("Failed notify_start: %s", exc)
            return False

    def send_text(
        self,
        token: str,
        to_user_id: str,
        text: str,
        base_url: str | None = None,
    ) -> bool:
        """Send a direct text message to the authorized user friend."""
        if not token or not to_user_id or not text.strip():
            return False
        req_base = (base_url or self.base_url).rstrip("/")
        url = f"{req_base}/ilink/bot/sendmessage"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "msg_type": 2,
                "item_list": [
                    {
                        "type": 1,
                        "text_item": {
                            "text": text,
                        },
                    }
                ],
            },
            "base_info": self._base_info(),
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=self._headers(token))
                if resp.status_code == 200:
                    data = resp.json()
                    ret = data.get("ret")
                    if ret in (0, None):
                        logger.info("Delivered ClawBot message to %s", to_user_id[:8] + "...")
                        return True
                    logger.warning("ClawBot send returned ret=%s errmsg=%s", ret, data.get("errmsg"))
                else:
                    logger.error("ClawBot send HTTP %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Exception in ClawBot send_text: %s", exc)
            return False

    def get_updates(
        self,
        token: str,
        cursor: str = "",
        base_url: str | None = None,
        long_poll_timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Long poll incoming messages from users."""
        req_base = (base_url or self.base_url).rstrip("/")
        url = f"{req_base}/ilink/bot/getupdates"
        payload = {
            "get_updates_buf": cursor,
            "base_info": self._base_info(),
        }
        try:
            with httpx.Client(timeout=long_poll_timeout + 5) as client:
                resp = client.post(url, json=payload, headers=self._headers(token))
                if resp.status_code == 200:
                    return resp.json()
                return {"ret": resp.status_code, "msgs": []}
        except httpx.TimeoutException:
            return {"ret": 0, "msgs": [], "get_updates_buf": cursor}
        except Exception as exc:
            logger.error("Exception in ClawBot get_updates: %s", exc)
            return {"ret": -1, "msgs": [], "error": str(exc)}
