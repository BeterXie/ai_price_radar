from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SourcePolicyRequestCreate, SourcePolicyRequestOut
from ..services.source_policy import create_policy_request


router = APIRouter(prefix="/api/v1/source-policy", tags=["source-policy"])


@router.post("/requests", response_model=SourcePolicyRequestOut, status_code=201)
def submit_source_policy_request(
    payload: SourcePolicyRequestCreate,
    db: Session = Depends(get_db),
):
    try:
        request = create_policy_request(
            db,
            source_url=payload.source_url,
            request_type=payload.request_type,
            requester_email=payload.requester_email,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return request
