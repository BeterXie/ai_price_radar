"""Read bounded probe SSE events; retain only timings and reported token counts."""
from __future__ import annotations

import json
import re
import time


def _token_count(value: object) -> int | None:
    # Counts must fit the database integer, and bool is not a token count.
    return value if type(value) is int and 0 <= value <= 2_147_483_647 else None


def input_usage(protocol: str, payload: dict) -> tuple[int | None, int | None]:
    usage = payload.get("usageMetadata" if protocol == "gemini" else "usage")
    if not isinstance(usage, dict):
        return None, None
    if protocol == "anthropic":
        plain = _token_count(usage.get("input_tokens"))
        read = _token_count(usage.get("cache_read_input_tokens"))
        written = _token_count(usage.get("cache_creation_input_tokens", 0))
        if plain is None or written is None:
            return None, None
        # A missing cache field is unknown, never evidence of a zero hit rate.
        if read is None:
            return None, None
        total = _token_count(plain + read + written)
    elif protocol == "gemini":
        total = _token_count(usage.get("promptTokenCount"))
        read = _token_count(usage.get("cachedContentTokenCount"))
    else:
        total = _token_count(usage.get("prompt_tokens"))
        details = usage.get("prompt_tokens_details")
        read = _token_count(details.get("cached_tokens")) if isinstance(details, dict) else None
    if total is None or (read is not None and read > total):
        return None, None
    # Keep a reported inclusive input count even if the cache breakdown is
    # absent. A separate accounting check may supply it; absence is never zero.
    return total, read


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class ProbeStream:
    def __init__(self, protocol: str, started: float):
        self.protocol = protocol
        self.started = started
        self.pending = b""
        self.data: list[bytes] = []
        self.has_text = False
        self.complete = False
        self.invalid = False
        self.first_token_ms: int | None = None
        self.input_tokens: int | None = None
        self.cached_input_tokens: int | None = None

    @property
    def healthy(self) -> bool:
        return self.has_text and self.complete and not self.invalid

    def feed(self, chunk: bytes) -> None:
        self.pending += chunk
        while match := re.search(rb"\r\n|\r|\n", self.pending):
            # A CRLF may straddle network reads.
            if match[0] == b"\r" and match.end() == len(self.pending):
                break
            line, self.pending = self.pending[:match.start()], self.pending[match.end():]
            if not line:
                if self.data:
                    self._event(b"\n".join(self.data))
                    self.data.clear()
            elif line.startswith(b"data:"):
                self.data.append(line[5:].removeprefix(b" "))

    def finish(self) -> None:
        # Resolve a final CR delimiter, but never dispatch data missing its
        # event separator. Even after a completion marker, a truncated error
        # or trailing data event means the response was not complete.
        if self.pending.endswith(b"\r"):
            self.feed(b"\n")
        if self.data or self.pending.strip():
            self.invalid = True

    def _event(self, data: bytes) -> None:
        if data == b"[DONE]" and self.protocol == "openai":
            self.complete = True
            return
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError, RecursionError):
            self.invalid = True
            return
        if not isinstance(payload, dict) or payload.get("error") or payload.get("type") == "error":
            self.invalid = True
            return
        text = False
        usage_payload = payload
        if self.protocol == "anthropic":
            event_type = payload.get("type")
            delta = payload.get("delta")
            if event_type == "content_block_delta" and isinstance(delta, dict):
                text = delta.get("type") == "text_delta" and _has_text(delta.get("text"))
            block = payload.get("content_block")
            if event_type == "content_block_start" and isinstance(block, dict):
                text = block.get("type") == "text" and _has_text(block.get("text"))
            if event_type == "message_start" and isinstance(payload.get("message"), dict):
                usage_payload = payload["message"]
            if event_type == "message_stop":
                self.complete = True
        elif self.protocol == "gemini":
            candidates = payload.get("candidates")
            for candidate in candidates if isinstance(candidates, list) else []:
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content")
                parts = content.get("parts") if isinstance(content, dict) else None
                text |= isinstance(parts, list) and any(
                    isinstance(part, dict) and not part.get("thought") and _has_text(part.get("text"))
                    for part in parts
                )
                if candidate.get("finishReason") in ("STOP", "MAX_TOKENS"):
                    self.complete = True
        else:
            choices = payload.get("choices")
            text = isinstance(choices, list) and any(
                isinstance(choice, dict) and isinstance(choice.get("delta"), dict)
                and _has_text(choice["delta"].get("content"))
                for choice in choices
            )
        if text:
            self.has_text = True
            if self.first_token_ms is None:
                self.first_token_ms = max(0, round((time.monotonic() - self.started) * 1000))
        total, cached = input_usage(self.protocol, usage_payload)
        if total is not None and (cached is not None or total != self.input_tokens):
            self.input_tokens, self.cached_input_tokens = total, cached
