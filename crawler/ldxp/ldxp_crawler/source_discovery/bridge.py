from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class DiscoveryBridgeError(RuntimeError):
    pass


class DiscoveryBridge:
    def __init__(self, base_url: str, worker_key: str, *, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.worker_key = worker_key
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.worker_key)

    def _request(self, path: str, payload: dict[str, Any]) -> Any:
        if not self.enabled:
            raise DiscoveryBridgeError("discovery bridge is not configured")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/")),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Discovery-Worker-Key": self.worker_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise DiscoveryBridgeError(f"discovery API returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DiscoveryBridgeError(f"discovery API request failed: {type(exc).__name__}") from exc

    def create_run(self, *, trigger: str, adapters: list[str]) -> int:
        result = self._request(
            "/api/v1/internal/source-discovery/runs",
            {"trigger": trigger, "adapters": adapters},
        )
        run_id = result.get("run_id") if isinstance(result, dict) else None
        if not isinstance(run_id, int):
            raise DiscoveryBridgeError("discovery API returned an invalid run response")
        return run_id

    def batch_upsert(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            return []
        result = self._request(
            "/api/v1/internal/source-candidates/batch",
            {"items": items},
        )
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise DiscoveryBridgeError("discovery API returned an invalid batch response")
        return [item for item in result["items"] if isinstance(item, dict)]

    def finish_run(self, run_id: int, payload: dict[str, Any]) -> None:
        self._request(f"/api/v1/internal/source-discovery/runs/{run_id}/finish", payload)

    def upsert(self, *, discovered_url: str, platform_hint: str, discovered_by: str, matched_query: str = "") -> dict[str, Any]:
        return self._request(
            "/api/v1/internal/source-candidates/upsert",
            {
                "discovered_url": discovered_url,
                "platform_hint": platform_hint,
                "discovered_by": discovered_by,
                "matched_query": matched_query,
            },
        )
