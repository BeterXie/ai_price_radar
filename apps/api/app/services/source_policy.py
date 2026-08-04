from __future__ import annotations

import urllib.parse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SourceIntake, SourcePolicyControl, SourcePolicyRequest
from .source_discovery import candidate_origin
from .source_intake import utcnow
from .source_platform import normalize_public_https_url


EMERGENCY_STOP_KEY = "emergency_stop"


def _request_origin(source_url: str) -> str:
    return candidate_origin(normalize_public_https_url(source_url))


def _ldxp_shop_token(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.rstrip("/").split("/") if part]
    if len(parts) == 2 and parts[0].casefold() == "shop":
        return parts[1].casefold()
    return ""


def create_policy_request(
    db: Session,
    *,
    source_url: str,
    request_type: str,
    requester_email: str,
    reason: str,
) -> SourcePolicyRequest:
    normalized = normalize_public_https_url(source_url)
    request = SourcePolicyRequest(
        source_url=normalized,
        request_type=request_type,
        requester_email=requester_email.strip()[:200],
        reason=reason.strip()[:2000],
        status="pending",
        temporary_hold_at=utcnow(),
    )
    db.add(request)
    db.commit()
    return request


def _disable_matching_intakes(db: Session, source_url: str) -> int:
    request_token = _ldxp_shop_token(normalize_public_https_url(source_url))
    request_normalized = normalize_public_https_url(source_url)
    now = utcnow()
    disabled = 0
    intakes = list(
        db.scalars(
            select(SourceIntake).where(
                SourceIntake.status.notin_({"disabled", "rejected"})
            )
        )
    )
    for intake in intakes:
        try:
            intake_normalized = normalize_public_https_url(intake.source_url)
        except ValueError:
            continue
        intake_token = _ldxp_shop_token(intake_normalized)
        if request_token:
            if intake_token != request_token:
                continue
        elif intake_normalized != request_normalized:
            continue
        intake.status = "disabled"
        intake.decision_note = f"商家退出收录（policy request）\n{intake.decision_note}".strip()
        intake.finished_at = now
        disabled += 1
    return disabled


def decide_policy_request(
    db: Session,
    request_id: int,
    *,
    decision: str,
    note: str,
) -> SourcePolicyRequest:
    request = db.get(SourcePolicyRequest, request_id)
    if request is None:
        raise LookupError("policy request not found")
    if request.status in {"applied", "rejected"}:
        raise ValueError(f"policy request is already {request.status}")
    request.status = decision
    request.decided_at = utcnow()
    request.decision_note = note.strip()[:1000]
    if decision == "applied":
        _disable_matching_intakes(db, request.source_url)
    db.commit()
    return request


def emergency_stop(db: Session, *, reason: str) -> None:
    row = db.get(SourcePolicyControl, EMERGENCY_STOP_KEY)
    if row is None:
        row = SourcePolicyControl(key=EMERGENCY_STOP_KEY, value=reason.strip()[:1000], updated_at=utcnow())
        db.add(row)
    else:
        row.value = reason.strip()[:1000]
        row.updated_at = utcnow()
    db.commit()


def resume_collection(db: Session, *, note: str) -> None:
    row = db.get(SourcePolicyControl, EMERGENCY_STOP_KEY)
    if row is not None:
        db.delete(row)
        db.commit()


def emergency_stop_reason(db: Session) -> str:
    row = db.get(SourcePolicyControl, EMERGENCY_STOP_KEY)
    return row.value if row is not None else ""


def policy_check(db: Session, source_url: str) -> dict[str, object]:
    """Fail-closed policy signal consumed by the crawler before any shop request."""
    emergency = bool(emergency_stop_reason(db))
    try:
        normalized = normalize_public_https_url(source_url)
    except ValueError:
        return {"emergency_stopped": emergency, "source_status": "invalid", "allowed": False}
    token = _ldxp_shop_token(normalized)
    request = None
    for candidate in db.scalars(select(SourcePolicyRequest).order_by(SourcePolicyRequest.id.desc())):
        try:
            candidate_normalized = normalize_public_https_url(candidate.source_url)
        except ValueError:
            continue
        candidate_token = _ldxp_shop_token(candidate_normalized)
        if token and candidate_token:
            if candidate_token == token:
                request = candidate
                break
        elif candidate_normalized == normalized:
            request = candidate
            break
    source_status = "active"
    if request is not None:
        if request.status in {"pending", "verified"}:
            source_status = "legal_hold"
        elif request.status == "applied":
            source_status = "opted_out"
    allowed = not emergency and source_status == "active"
    return {
        "emergency_stopped": emergency,
        "source_status": source_status,
        "allowed": allowed,
    }
