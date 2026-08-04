from __future__ import annotations

import re


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("wechat", re.compile(r"(?:微信|wechat|vx|wx)[:：\s]*[A-Za-z0-9_-]{6,20}", re.IGNORECASE)),
    ("qq", re.compile(r"(?<!\d)[1-9]\d{4,11}(?!\d)")),
    ("telegram", re.compile(r"t\.me/[\w-]{4,}", re.IGNORECASE)),
    ("api_key", re.compile(r"(?i)(?:api[_-]?key|token|secret|bearer)[=:：\s]+[A-Za-z0-9_\-\.]{8,}")),
    ("cookie", re.compile(r"(?i)(?:cookie|sessionid|jsessionid)[=:：\s]+[^;\s]{8,}")),
    ("card_code", re.compile(r"(?i)(?:卡密|cdk|兑换码)[:：\s]*[A-Za-z0-9-]{8,}")),
    ("account_password", re.compile(r"(?i)(?:账号|用户名|邮箱)[:：\s]*\S+\s*(?:密码|password)[:：\s]*\S+")),
    ("bank_card", re.compile(r"(?<!\d)(?:62|60|4|5)\d{13,18}(?!\d)")),
    ("id_card", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")),
]


def sensitive_hits(value: object) -> list[str]:
    text = str(value or "")
    return [label for label, pattern in _PATTERNS if pattern.search(text)]


def redact_text(value: object) -> tuple[str, list[str]]:
    text = str(value or "")
    hits = sensitive_hits(text)
    if not hits:
        return text, []
    redacted = text
    for _label, pattern in _PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted, hits
