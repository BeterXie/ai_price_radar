import json

import pytest

from app.services.relay_probe_metrics import ProbeStream, input_usage


def event(payload):
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode() + b"\r\n\r\n"


@pytest.mark.parametrize(("protocol", "payload", "expected"), [
    ("openai", {"usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 80}}}, (100, 80)),
    ("openai", {"usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 0}}}, (100, 0)),
    ("anthropic", {"usage": {"input_tokens": 10, "cache_read_input_tokens": 80, "cache_creation_input_tokens": 10}}, (100, 80)),
    ("gemini", {"usageMetadata": {"promptTokenCount": 100, "cachedContentTokenCount": 80}}, (100, 80)),
    ("openai", {"usage": {"prompt_tokens": 100}}, (None, None)),
    ("anthropic", {"usage": {"input_tokens": 100}}, (None, None)),
    ("gemini", {"usageMetadata": {"promptTokenCount": 100}}, (None, None)),
    ("openai", {"usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 101}}}, (None, None)),
    ("gemini", {"usageMetadata": {"promptTokenCount": True, "cachedContentTokenCount": 0}}, (None, None)),
    ("anthropic", {"usage": {"input_tokens": 2_147_483_647, "cache_read_input_tokens": 5}}, (None, None)),
])
def test_cache_usage_is_explicit_valid_and_normalized(protocol, payload, expected):
    assert input_usage(protocol, payload) == expected


def test_openai_timing_ignores_roles_heartbeats_and_handles_split_utf8(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("app.services.relay_probe_metrics.time.monotonic", lambda: clock[0])
    stream = ProbeStream("openai", 10.0)
    stream.feed(b": keepalive\n\n" + event({"choices": [{"delta": {"role": "assistant", "content": ""}}]}))
    assert stream.first_token_ms is None
    clock[0] = 10.125
    body = event({"choices": [{"delta": {"content": "你好"}}]})
    for byte in body:
        stream.feed(bytes([byte]))
    assert stream.first_token_ms == 125
    clock[0] = 10.9
    stream.feed(event({"choices": [], "usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 80}}}))
    assert not stream.healthy  # EOF before [DONE] must not pass.
    stream.feed(b"data: [DONE]\n\n")
    assert stream.healthy
    assert (stream.input_tokens, stream.cached_input_tokens) == (100, 80)
    assert stream.first_token_ms == 125


def test_anthropic_usage_survives_output_only_message_delta():
    stream = ProbeStream("anthropic", 0)
    stream.feed(event({"type": "message_start", "message": {"usage": {"input_tokens": 20, "cache_read_input_tokens": 80, "cache_creation_input_tokens": 100}}}))
    stream.feed(event({"type": "ping"}))
    stream.feed(event({"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "hidden"}}))
    assert stream.first_token_ms is None
    stream.feed(event({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "OK"}}))
    stream.feed(event({"type": "message_delta", "usage": {"output_tokens": 3}}))
    stream.feed(event({"type": "message_stop"}))
    assert stream.healthy
    assert (stream.input_tokens, stream.cached_input_tokens) == (200, 80)


def test_gemini_thoughts_are_not_first_output_and_usage_is_not_summed():
    stream = ProbeStream("gemini", 0)
    stream.feed(event({"candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}]}}]}))
    assert stream.first_token_ms is None
    stream.feed(event({"candidates": [{"content": {"parts": [{"text": "OK"}]}}], "usageMetadata": {"promptTokenCount": 100, "cachedContentTokenCount": 50}}))
    stream.feed(event({"candidates": [{"finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 100, "cachedContentTokenCount": 60}}))
    assert stream.healthy
    assert (stream.input_tokens, stream.cached_input_tokens) == (100, 60)


@pytest.mark.parametrize("tail", [b'data: {"error":{"message":"secret"}}\n\n', b"data: invalid\n\n", b"data: []\n\n"])
def test_stream_error_or_malformed_event_after_text_fails(tail):
    stream = ProbeStream("openai", 0)
    stream.feed(event({"choices": [{"delta": {"content": "OK"}}]}) + tail + b"data: [DONE]\n\n")
    assert not stream.healthy


def test_sse_multiline_data_and_cr_delimiters():
    stream = ProbeStream("openai", 0)
    stream.feed(b'data: {"choices":\ndata: [{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\r\r')
    stream.finish()
    assert stream.healthy


@pytest.mark.parametrize("tail", [
    b'data: {"error":{"message":"failed"}}\n',
    b'data: {"error":',
    b'data: {"choices":[]}\n',
])
def test_eof_after_completion_rejects_incomplete_trailing_events(tail):
    stream = ProbeStream("openai", 0)
    stream.feed(event({"choices": [{"delta": {"content": "OK"}}]}) + b"data: [DONE]\n\n" + tail)
    stream.finish()
    assert not stream.healthy
