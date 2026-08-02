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

    def _request(self, path: str, payload: dict[str, Any]) -> Any:
        if not self.enabled:
            raise IntakeBridgeError("intake bridge is not configured")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/")),
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
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise IntakeBridgeError(f"intake API returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise IntakeBridgeError(f"intake API request failed: {type(exc).__name__}") from exc

    def claim(self, *, limit: int, lease_seconds: int) -> list[dict[str, Any]]:
        result = self._request(
            "/api/v1/internal/source-intakes/claim",
            {"limit": limit, "lease_seconds": lease_seconds},
        )
        if not isinstance(result, list):
            raise IntakeBridgeError("intake API returned an invalid claim response")
        return [item for item in result if isinstance(item, dict)]

    def report_result(
        self,
        *,
        intake_id: int,
        attempt_count: int,
        status: str,
        product_count: int = 0,
        failure_reason: str = "",
    ) -> dict[str, Any]:
        result = self._request(
            f"/api/v1/internal/source-intakes/{intake_id}/result",
            {
                "status": status,
                "attempt_count": attempt_count,
                "product_count": product_count,
                "failure_reason": failure_reason,
            },
        )
        if not isinstance(result, dict):
            raise IntakeBridgeError("intake API returned an invalid result response")
        return result
