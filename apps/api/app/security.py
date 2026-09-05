from hmac import compare_digest

from fastapi import Header, HTTPException, status

from .core.config import get_settings


def _configured(key: str) -> bool:
    return bool(key.strip()) and not key.startswith("replace-with-")


def require_admin(x_admin_key: str = Header(default="")) -> None:
    expected = get_settings().admin_api_key
    if not _configured(expected) or not compare_digest(x_admin_key.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


def require_intake_worker(x_intake_worker_key: str = Header(default="")) -> None:
    expected = get_settings().intake_worker_key
    if not _configured(expected):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="intake worker is not configured")
    if not compare_digest(x_intake_worker_key.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid intake worker key")


def require_detector_worker(x_detector_worker_key: str = Header(default="")) -> None:
    expected = get_settings().detector_worker_key
    if not _configured(expected):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="detector worker is not configured")
    if not compare_digest(x_detector_worker_key.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid detector worker key")


def require_discovery_worker(x_discovery_worker_key: str = Header(default="")) -> None:
    expected = get_settings().discovery_worker_key
    if not _configured(expected):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="discovery worker is not configured")
    if not compare_digest(x_discovery_worker_key.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid discovery worker key")
