"""Official 16688 domain transition; merchant and product IDs do not change."""
from urllib.parse import urlsplit


HOSTS = frozenset({"16688.store", "www.16688.store", "16688.com.cn", "www.16688.com.cn"})
ORIGIN = "https://www.16688.store"


def canonical_url(value: str) -> str:
    """Use the current www origin directly, preserving paths and IDs."""
    parsed = urlsplit(value)
    if (parsed.hostname not in HOSTS or parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)):
        return value
    return parsed._replace(netloc="www.16688.store").geturl()
