import re


_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL = re.compile(rf"[A-Za-z0-9_+-]+(?:\.[A-Za-z0-9_+-]+)*@(?:{_LABEL}\.)+{_LABEL}")


def normalize_email(value: str) -> str:
    address = str(value or "").strip()
    if len(address) > 200 or len(address.partition("@")[0]) > 64 or _EMAIL.fullmatch(address) is None:
        raise ValueError("a valid email address is required")
    return address
