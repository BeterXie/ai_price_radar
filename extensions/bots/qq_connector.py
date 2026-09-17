"""Official Tencent QQ Bot Connector Client.

Implements the zero-threshold official Tencent QQ Connector protocol:
Reference: Dota AI Decision Lab (@tencent-connect/qqbot-connector)
1. Requests bind task from https://q.qq.com/lite/create_bind_task
2. Generates Mobile QQ authorization URL: https://q.qq.com/qqbot/openclaw/connect.html?task_id=...&source=&_wv=2
3. User scans QR code with Phone QQ (手机 QQ 扫一扫).
4. Polls https://q.qq.com/lite/poll_bind_result
5. When status == 2 (COMPLETED), decrypts bot_encrypt_secret using AES-256-GCM.
6. Yields app_id, app_secret, user_openid for instant QQ message dispatch.
"""

from __future__ import annotations

import base64
import logging
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx

logger = logging.getLogger(__name__)

QQ_HOST = "q.qq.com"
CREATE_BIND_TASK_URL = f"https://{QQ_HOST}/lite/create_bind_task"
POLL_BIND_RESULT_URL = f"https://{QQ_HOST}/lite/poll_bind_result"


class QQConnectorClient:
    """Python client implementing Tencent QQ Connector protocol."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def start_bind_task(self) -> dict[str, Any]:
        """Create a new binding task on Tencent QQ.

        Returns:
            {"task_id": "...", "key": "...", "qrcode_url": "https://q.qq.com/..."}
        """
        # 32 random bytes for AES-256-GCM
        key_bytes = secrets.token_bytes(32)
        key_b64 = base64.b64encode(key_bytes).decode("ascii")

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    CREATE_BIND_TASK_URL,
                    json={"key": key_b64},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                if resp.status_code != 200:
                    logger.error("create_bind_task returned %d: %s", resp.status_code, resp.text)
                    return {}

                data = resp.json()
                if data.get("retcode") != 0 or not data.get("data", {}).get("task_id"):
                    logger.error("create_bind_task error payload: %s", data)
                    return {}

                task_id = data["data"]["task_id"]
                connect_url = f"https://{QQ_HOST}/qqbot/openclaw/connect.html?task_id={task_id}&source=&_wv=2"
                return {
                    "task_id": task_id,
                    "key": key_b64,
                    "qrcode_url": connect_url,
                }
        except Exception as exc:
            logger.error("Failed to start QQ bind task: %s", exc)
            return {}

    def poll_bind_task(self, task_id: str, key_b64: str) -> dict[str, Any]:
        """Poll task result and decrypt credentials if completed.

        Status codes from Tencent:
        0: NONE
        1: PENDING (Waiting for user scan in Phone QQ)
        2: COMPLETED (Scanned and authorized!)
        3: EXPIRED
        """
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    POLL_BIND_RESULT_URL,
                    json={"task_id": task_id},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                if resp.status_code != 200:
                    return {"status": "ERROR", "message": f"HTTP {resp.status_code}"}

                payload = resp.json()
                if payload.get("retcode") != 0:
                    return {"status": "ERROR", "message": payload.get("msg", "poll failed")}

                data = payload.get("data", {})
                st = data.get("status")

                if st == 1:
                    return {"status": "PENDING"}
                elif st == 2:
                    # Completed! Decrypt secret
                    bot_appid = str(data.get("bot_appid", "")).strip()
                    encrypted_secret = data.get("bot_encrypt_secret", "")
                    user_openid = str(data.get("user_openid", "")).strip()

                    app_secret = ""
                    if encrypted_secret and key_b64:
                        try:
                            app_secret = self.decrypt_secret(encrypted_secret, key_b64)
                        except Exception as dec_err:
                            logger.error("Failed decrypting bot secret: %s", dec_err)

                    return {
                        "status": "COMPLETED",
                        "app_id": bot_appid,
                        "app_secret": app_secret,
                        "user_openid": user_openid,
                    }
                elif st == 3:
                    return {"status": "EXPIRED"}
                else:
                    return {"status": "PENDING"}
        except Exception as exc:
            logger.debug("Error polling QQ bind task: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    @staticmethod
    def decrypt_secret(encrypted_b64: str, key_b64: str) -> str:
        """Decrypt AES-256-GCM secret matching Tencent qqbot-connector implementation."""
        key_bytes = base64.b64decode(key_b64)
        raw_bytes = base64.b64decode(encrypted_b64)

        # Tencent layout:
        # nonce: first 12 bytes
        # ciphertext + auth_tag: remaining bytes (last 16 bytes is tag)
        nonce = raw_bytes[:12]
        ciphertext_and_tag = raw_bytes[12:]

        aesgcm = AESGCM(key_bytes)
        decrypted = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        return decrypted.decode("utf-8")
