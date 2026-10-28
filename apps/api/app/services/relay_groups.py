"""Read whitelisted group metadata, without storing balances or raw responses."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from http.client import HTTPException

from ..schemas import RelayGroupConfig
from .relay_models import CatalogResponseError, _text
from .relay_monitor import ProbeTarget


def _ratio(value: object) -> float | None:
    if type(value) not in (float, int):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _billing_groups(payload: dict, key: str) -> list[dict]:
    rows = payload.get("groups")
    if "groups" in payload and not isinstance(rows, list):
        raise CatalogResponseError("invalid_response")
    if rows is None:
        rows = [payload] if "group_rate_multiplier" in payload else []
    if len(rows) > 100:
        raise CatalogResponseError("invalid_response")
    groups = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CatalogResponseError("invalid_response")
        if row.get("status", "active") != "active":
            continue
        group_id = row.get("group_id")
        name = _text(row.get("group_name"), key)
        identity = str(group_id) if type(group_id) is int else name or "current-key"
        groups[identity] = {
            "id": identity, "name": name or "当前密钥分组",
            "ratio": _ratio(row.get("group_rate_multiplier")),
            "effective_ratio": _ratio(row.get("effective_rate_multiplier")),
            "description": "", "models": None,
        }
    if not groups and "groups" not in payload:
        raise CatalogResponseError("invalid_response")
    return list(groups.values())


def _pricing_groups(payload: dict, key: str) -> list[dict]:
    ratios = payload.get("group_ratio")
    if not isinstance(ratios, dict):
        raise CatalogResponseError("unsupported")
    if len(ratios) > 100:
        raise CatalogResponseError("invalid_response")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise CatalogResponseError("invalid_response")
    groups = []
    for identity, value in ratios.items():
        identity = _text(identity, key)
        if not identity:
            raise CatalogResponseError("invalid_response")
        info = value if isinstance(value, dict) else {}
        ratio = info.get("GroupRatio", info.get("group_ratio", info.get("ratio"))) if info else value
        # Never infer a default group or treat an omitted membership as empty.
        membership_known = all(isinstance(row, dict) and isinstance(row.get("enable_groups"), list) for row in rows)
        models = None
        if membership_known:
            models = list(dict.fromkeys(_text(row.get("model_name"), key, 200) for row in rows if identity in row["enable_groups"]))
            models = [model for model in models if model]
            if len(models) > 2000:
                raise CatalogResponseError("invalid_response")
        groups.append({
            "id": identity,
            "name": _text(info.get("DisplayName", info.get("display_name")), key) or identity,
            "ratio": _ratio(ratio), "effective_ratio": None,
            "description": _text(info.get("Description", info.get("description")), key, 500),
            "models": models,
        })
    return groups


def _plaza_groups(payload: dict, key: str) -> list[dict]:
    data = payload.get("data")
    if "code" not in payload or not isinstance(data, dict) or "groups" not in data:
        raise CatalogResponseError("unsupported")
    if type(payload["code"]) is not int or payload["code"] != 0:
        raise CatalogResponseError("invalid_response")
    rows = data["groups"]
    if not isinstance(rows, list) or len(rows) > 100:
        raise CatalogResponseError("invalid_response")
    groups = []
    for row in rows:
        if not isinstance(row, dict):
            raise CatalogResponseError("invalid_response")
        if row.get("is_exclusive") is True:
            continue
        identity = row.get("id")
        name = _text(row.get("name"), key)
        if type(identity) is not int or identity <= 0 or not name:
            raise CatalogResponseError("invalid_response")
        models = None
        if "models" in row:
            if not isinstance(row["models"], list) or len(row["models"]) > 2000:
                raise CatalogResponseError("invalid_response")
            models = []
            for model in row["models"]:
                model_id = _text(model.get("name"), key, 200) if isinstance(model, dict) else ""
                if not model_id:
                    raise CatalogResponseError("invalid_response")
                models.append(model_id)
        groups.append({
            "id": str(identity), "name": name,
            "ratio": _ratio(row.get("rate_multiplier")), "effective_ratio": None,
            "description": _text(row.get("description"), key, 500),
            "models": models,
        })
    return groups


def fetch_group_catalog(target: ProbeTarget, key: str, *, client=None) -> dict:
    from price_radar_http import PinnedHTTPSClient

    checked = datetime.now(timezone.utc).isoformat()
    result = {"status": "config_error", "checked_at": checked}
    if not key:
        return result
    base = target.base_url.rstrip("/")
    if base.endswith(("/v1", "/v1beta")):
        base = base.rsplit("/", 1)[0]
    # Same configured host and prefix only; redirects are rejected by the client.
    client = client or PinnedHTTPSClient(
        max_response_bytes=1024 * 1024, max_task_bytes=3 * 1024 * 1024,
        max_task_seconds=45, request_timeout=30,
    )
    try:
        # The anonymous plaza describes the site's public groups. Billing only
        # describes this key, so a successful billing response cannot stand in
        # for the public directory. Never send the key or a panel JWT here.
        response = client.get(base + "/api/v1/model-plaza", accept="application/json", headers={})
        groups = None
        if response.status_code not in (401, 403, 404, 405):
            if not 200 <= response.status_code < 300:
                raise CatalogResponseError("upstream_error")
            # Some sites serve their SPA for unknown API paths.
            if "text/html" not in response.headers.get("content-type", "").lower():
                payload = json.loads(response.body)
                if isinstance(payload, dict):
                    try:
                        groups = _plaza_groups(payload, key)
                    except CatalogResponseError as exc:
                        if exc.status != "unsupported":
                            raise
        if groups is not None:
            groups = RelayGroupConfig.model_validate({"groups": groups}).model_dump()["groups"]
            result.update(status="ok", source="public_model_plaza", synced_at=checked, groups=groups)
            return result

        response = client.get(base + "/v1/sub2api/billing", accept="application/json", headers={"Authorization": "Bearer " + key})
        if response.status_code in (404, 405):
            # New API pricing is public. Do not send the configured key to a
            # management endpoint that may use a different authentication scheme.
            response = client.get(base + "/api/pricing", accept="application/json", headers={})
            source, parse = "public_pricing", _pricing_groups
        else:
            source, parse = "key_billing", _billing_groups
        if response.status_code in (401, 403):
            raise CatalogResponseError("credential_error")
        if not 200 <= response.status_code < 300:
            raise CatalogResponseError("unsupported" if response.status_code in (404, 405) else "upstream_error")
        payload = json.loads(response.body)
        if not isinstance(payload, dict) or payload.get("error"):
            raise CatalogResponseError("invalid_response")
        groups = RelayGroupConfig.model_validate({"groups": parse(payload, key)}).model_dump()["groups"]
        result.update(status="ok", source=source, synced_at=checked, groups=groups)
    except CatalogResponseError as exc:
        result["status"] = exc.status
    except TimeoutError:
        result["status"] = "timeout"
    except (OSError, HTTPException):
        result["status"] = "connection_error"
    except (ValueError, TypeError, RecursionError, OverflowError):
        result["status"] = "invalid_response"
    return result
