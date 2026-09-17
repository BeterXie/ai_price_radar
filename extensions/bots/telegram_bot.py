from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Telegram Bot API client exclusively for administrator/owner alerts.

    Per specification, this channel is NOT open to public users.
    """

    def __init__(
        self,
        token: str | None = None,
        admin_chat_id: str | None = None,
        base_url: str | None = None,
        proxy: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.token = (token or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
        self.admin_chat_id = (admin_chat_id or os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")).strip()
        self.base_url = (base_url or os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")).rstrip("/")
        self.proxy = (proxy or os.getenv("TELEGRAM_PROXY", "")).strip() or None
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.admin_chat_id)

    def send_admin_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to administrator via sync HTTP request."""
        if not self.is_configured:
            logger.debug("Telegram bot is not configured (token or admin_chat_id missing)")
            return False

        url = f"{self.base_url}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds, proxy=self.proxy) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram admin notification delivered successfully")
                    return True
                logger.error("Telegram API returned error %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Failed to send Telegram notification: %s", exc)
            return False

    async def send_admin_message_async(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to administrator via async HTTP request."""
        if not self.is_configured:
            logger.debug("Telegram bot is not configured (token or admin_chat_id missing)")
            return False

        url = f"{self.base_url}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.admin_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, proxy=self.proxy) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram admin notification delivered successfully (async)")
                    return True
                logger.error("Telegram API returned error %d: %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.error("Failed to send Telegram notification (async): %s", exc)
            return False

    def handle_incoming_message(self, chat_id: str | int, text: str, db_session: Any = None) -> str:
        """Handle incoming command from Telegram admin, query price or status, and reply."""
        from .chat_commands import handle_chat_command

        reply = handle_chat_command(text, sender_id=str(chat_id), channel="telegram", db=db_session)
        if chat_id and self.is_configured:
            try:
                self.send_admin_message(reply, parse_mode="")
            except Exception as exc:
                logger.error("Failed sending reply to Telegram: %s", exc)
        return reply
