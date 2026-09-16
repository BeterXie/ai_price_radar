from hmac import compare_digest

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .core.config import get_settings
from .database import get_db
from .models import User


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


def get_token_from_request(request: Request) -> str:
    settings = get_settings()
    # 1. Check cookie
    token = request.cookies.get(settings.session_cookie_name) or ""
    if token:
        return token
    # 2. Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return ""


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    token = get_token_from_request(request)
    if not token:
        return None
    from .services.auth import get_user_by_session_token
    return get_user_by_session_token(db, token)


def require_current_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return user
