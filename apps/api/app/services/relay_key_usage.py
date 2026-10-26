"""Reconcile one probe with Sub2API's API-key counters; never retain account data."""
from __future__ import annotations

import json
from dataclasses import dataclass
from http.client import HTTPException


@dataclass(frozen=True)
class KeyUsage:
    requests: int
    input_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


def _valid_counter(value: object) -> bool:
    # Lifetime counters can exceed a probe's 32-bit database columns.
    return type(value) is int and 0 <= value <= 9_223_372_036_854_775_807


def read_key_usage(base_url: str, key: str, *, client=None) -> KeyUsage | None:
    from price_radar_http import PinnedHTTPSClient

    base = base_url.rstrip("/")
    base = base if base.endswith("/v1") else base + "/v1"
    try:
        client = client or PinnedHTTPSClient(
            max_response_bytes=128 * 1024, max_task_bytes=128 * 1024,
            max_task_seconds=5, request_timeout=3,
        )
        response = client.get(base + "/usage", accept="application/json", headers={"Authorization": "Bearer " + key})
        if response.status_code != 200:
            return None
        payload = json.loads(response.body)
        if not isinstance(payload, dict) or payload.get("error") or payload.get("isValid") is False:
            return None
        usage = payload.get("usage")
        total = usage.get("total") if isinstance(usage, dict) else None
        if not isinstance(total, dict):
            return None
        values = {name: total.get(name) for name in KeyUsage.__dataclass_fields__}
        if not all(_valid_counter(value) for value in values.values()):
            return None
        return KeyUsage(**values)
    except (OSError, ValueError, TypeError, RecursionError, HTTPException, RuntimeError):
        # Optional accounting must not change probe health or expose raw errors.
        return None


def probe_usage(before: KeyUsage, after: KeyUsage | None, reported_input: int | None) -> tuple[int | None, int | None]:
    if after is None or type(reported_input) is not int or not 0 < reported_input <= 2_147_483_647:
        return None, None
    if after.requests - before.requests != 1:
        return None, None  # Concurrent calls or delayed accounting cannot be attributed.
    plain = after.input_tokens - before.input_tokens
    read = after.cache_read_tokens - before.cache_read_tokens
    written = after.cache_creation_tokens - before.cache_creation_tokens
    # Sub2API's three input buckets are disjoint. Match the model response's
    # inclusive input count before attributing any delta to this probe.
    if min(plain, read, written) < 0 or plain + read + written != reported_input:
        return None, None
    return reported_input, read
