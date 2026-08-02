from fastapi import Header, HTTPException, status

from .core.config import get_settings


def require_admin(x_admin_key: str = Header(default="")) -> None:
    expected = get_settings().admin_api_key
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


def require_intake_worker(x_intake_worker_key: str = Header(default="")) -> None:
    expected = get_settings().intake_worker_key
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="intake worker is not configured")
    if x_intake_worker_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid intake worker key")
