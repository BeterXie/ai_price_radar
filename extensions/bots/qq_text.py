import re


def normalize_qq_text(value: str) -> str:
    """Strip transport mentions, including opaque OpenIDs, before routing."""
    text = re.sub(r"<@!?[A-Za-z0-9_-]+>", " ", value or "").strip()
    return re.sub(r"^@[^\s]+\s*", "", text).strip()
