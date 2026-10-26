import json
from http.client import BadStatusLine

import pytest
from price_radar_http import PinnedResponse

from app.services.relay_key_usage import KeyUsage, probe_usage, read_key_usage


class UsageClient:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.calls = []

    def get(self, url, *, headers, accept):
        self.calls.append((url, headers, accept))
        if isinstance(self.payload, Exception):
            raise self.payload
        return PinnedResponse(self.status, {}, json.dumps(self.payload).encode())


def ledger(**values):
    return {"requests": 50, "input_tokens": 3_000_000_000, "cache_read_tokens": 200, "cache_creation_tokens": 10, **values}


@pytest.mark.parametrize("base", ["https://api.example.com/proxy", "https://api.example.com/proxy/v1/"])
def test_reads_only_lifetime_token_counters_from_configured_prefix(base):
    fake = UsageClient({"isValid": True, "balance": 999, "email": "private@example.com", "usage": {"total": ledger()}})
    result = read_key_usage(base, "test-secret", client=fake)
    assert result == KeyUsage(**ledger())
    assert fake.calls == [("https://api.example.com/proxy/v1/usage", {"Authorization": "Bearer test-secret"}, "application/json")]
    assert "balance" not in repr(result) and "private" not in repr(result) and "test-secret" not in repr(result)


@pytest.mark.parametrize("payload", [
    None, [], {"usage": []}, {"usage": {"today": ledger()}},
    {"error": "failed", "usage": {"total": ledger()}},
    {"isValid": False, "usage": {"total": ledger()}},
    *({"usage": {"total": ledger(cache_read_tokens=value)}} for value in (None, True, -1, "0", 0.5, 2**63)),
    {"usage": {"total": {key: value for key, value in ledger().items() if key != "cache_creation_tokens"}}},
])
def test_incomplete_or_invalid_accounting_never_becomes_zero(payload):
    assert read_key_usage("https://api.example.com/v1", "test-secret", client=UsageClient(payload)) is None


@pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
def test_unsupported_usage_endpoint_is_optional(status):
    assert read_key_usage("https://api.example.com/v1", "test-secret", client=UsageClient({}, status)) is None


@pytest.mark.parametrize("error", [TimeoutError("secret"), OSError("secret"), BadStatusLine("secret"), ValueError("secret")])
def test_optional_usage_failure_does_not_escape_or_log_secrets(error, caplog):
    assert read_key_usage("https://api.example.com", "test-secret", client=UsageClient(error)) is None
    assert "secret" not in caplog.text


@pytest.mark.parametrize(("plain", "cached", "written"), [(12, 0, 0), (2, 10, 0), (2, 8, 2)])
def test_single_request_delta_uses_disjoint_buckets_and_matches_response(plain, cached, written):
    before = KeyUsage(**ledger())
    after = KeyUsage(before.requests + 1, before.input_tokens + plain, before.cache_read_tokens + cached, before.cache_creation_tokens + written)
    assert probe_usage(before, after, 12) == (12, cached)


@pytest.mark.parametrize(("values", "reported"), [
    ({"requests": 50}, 12),  # Accounting has not included this probe yet.
    ({"requests": 52}, 12),  # Another call used this key.
    ({"requests": 49}, 12),  # Counter reset.
    ({"input_tokens": 2_999_999_999, "cache_read_tokens": 213}, 12),
    ({"cache_read_tokens": 199, "input_tokens": 3_000_000_013}, 12),
    ({"cache_creation_tokens": 9, "input_tokens": 3_000_000_013}, 12),
    ({}, 13), ({}, None), ({}, 0), ({}, True), ({}, 2**31),
])
def test_ambiguous_or_mismatched_delta_remains_unknown(values, reported):
    before = KeyUsage(**ledger())
    after = KeyUsage(**ledger(requests=51, input_tokens=3_000_000_012) | values)
    assert probe_usage(before, after, reported) == (None, None)
