from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class IntakeBridgeError(RuntimeError):
    pass


class IntakeBridge:
    def __init__(self, base_url: str, worker_key: str, *, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.worker_key = worker_key
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.worker_key)

    def onboard(self, *, intake_id: int, attempt_count: int, product_count: int) -> dict[str, Any]:
        if not self.enabled:
            raise IntakeBridgeError("intake bridge is not configured")
        body = json.dumps(
            {
                "status": "onboarded",
                "attempt_count": attempt_count,
                "product_count": product_count,
                "published": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            urllib.parse.urljoin(
                f"{self.base_url}/",
                f"api/v1/internal/source-intakes/{intake_id}/result",
            ),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Intake-Worker-Key": self.worker_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise IntakeBridgeError(f"intake API returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise IntakeBridgeError(f"intake API request failed: {type(exc).__name__}") from exc
        if not isinstance(result, dict):
            raise IntakeBridgeError("intake API returned an invalid onboarding response")
        return result
