from __future__ import annotations

import urllib.parse
from datetime import timedelta
import hashlib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SourceIntake, SourcePolicyControl, SourcePolicyEffect, SourcePolicyRequest
from .source_discovery import candidate_origin
from .source_intake import utcnow
from .source_platform import normalize_public_https_url


EMERGENCY_STOP_KEY = "emergency_stop"
LDXP_HOSTS = frozenset({"pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"})
LDXP_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")
ACTIVE_OPT_OUT_STATUSES = {"pending_unverified", "pending", "verified", "applied"}
UNVERIFIED_HOLD_HOURS = 24
VERIFIED_HOLD_DAYS = 7


def _request_origin(source_url: str) -> str:
    return candidate_origin(normalize_public_https_url(source_url))


def _aware(value: object, now: object) -> object:
    if value is None or getattr(value, "tzinfo", None) is not None:
        return value
    return value.replace(tzinfo=now.tzinfo)


def source_identity(url: str) -> tuple[str, str]:
    """Return a canonical source identity.

    Only the official LDXP hosts match by shop token; every other website is
    matched by its exact normalized URL so an attacker cannot freeze or disable
    a shop by submitting a look-alike path on a different domain.
    """
    normalized = normalize_public_https_url(url)
    parsed = urllib.parse.urlsplit(normalized)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host in LDXP_HOSTS:
        parts = [urllib.parse.unquote(part) for part in parsed.path.rstrip("/").split("/") if part]
        if len(parts) == 2 and parts[0].casefold() == "shop" and LDXP_TOKEN_RE.fullmatch(parts[1]):
            return ("ldxp", parts[1].casefold())
    return ("url", normalized)


def create_policy_request(
    db: Session,
    *,
    source_url: str,
    request_type: str,
    requester_email: str,
    reason: str,
    requester_ip: str = "",
) -> SourcePolicyRequest:
    normalized = normalize_public_https_url(source_url)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", requester_email.strip()):
        raise ValueError("requester_email must be a valid email address")
    now = utcnow()
    since = now - timedelta(hours=1)
    identity = source_identity(normalized)
    requester_ip = hashlib.sha256(requester_ip.encode("utf-8")).hexdigest() if requester_ip else ""
    existing = list(db.scalars(select(SourcePolicyRequest)))
    if request_type == "opt_out":
        for row in existing:
            try:
                row_normalized = normalize_public_https_url(row.source_url)
            except ValueError:
                continue
            if row.status in ACTIVE_OPT_OUT_STATUSES:
                if source_identity(row.source_url) == identity:
                    raise ValueError("an active opt-out already exists for this source")
    source_recent = sum(
        1
        for row in existing
        if _aware(row.created_at, now) >= since and _matches_source(row.source_url, normalized)
    )
    if source_recent >= 3:
        raise ValueError("too many requests for this source; try again later")
    email_recent = sum(
        1
        for row in existing
        if _aware(row.created_at, now) >= since and row.requester_email.casefold() == requester_email.strip().casefold()
    )
    if email_recent >= 3:
        raise ValueError("too many requests from this email; try again later")
    if requester_ip:
        ip_recent = sum(1 for row in existing if _aware(row.created_at, now) >= since and row.requester_ip == requester_ip)
        if ip_recent >= 10:
            raise ValueError("too many requests from this address; try again later")
    request = SourcePolicyRequest(
        source_url=normalized,
        request_type=request_type,
        requester_email=requester_email.strip()[:200],
        requester_ip=requester_ip[:64],
        reason=reason.strip()[:2000],
        status="pending_unverified" if request_type == "opt_out" else "pending",
        temporary_hold_at=now if request_type == "opt_out" else None,
    )
    db.add(request)
    db.commit()
    return request


def _matches_source(request_source_url: str, normalized: str) -> bool:
    try:
        return source_identity(request_source_url) == source_identity(normalized)
    except ValueError:
        return False


def _disable_matching_intakes(db: Session, source_url: str, *, policy_request_id: int) -> int:
    request_identity = source_identity(source_url)
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
            intake_identity = source_identity(intake.source_url)
        except ValueError:
            continue
        if request_identity[0] == "ldxp":
            if intake.source_type != "ldxp" or intake_identity != request_identity:
                continue
        elif intake_identity != request_identity:
            continue
        db.add(SourcePolicyEffect(
            policy_request_id=policy_request_id,
            intake_id=intake.id,
            previous_status=intake.status,
            applied_at=now,
        ))
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
    if decision == "applied" and request.request_type != "opt_out":
        request.status = "applied"
        request.decided_at = utcnow()
        request.decision_note = note.strip()[:1000]
        db.commit()
        return request
    request.status = decision
    request.decided_at = utcnow()
    request.decision_note = note.strip()[:1000]
    if decision == "applied" and request.request_type == "opt_out":
        _disable_matching_intakes(db, request.source_url, policy_request_id=request.id)
    db.commit()
    return request


def reverse_applied_opt_out(db: Session, request_id: int, *, note: str) -> SourcePolicyRequest:
    request = db.get(SourcePolicyRequest, request_id)
    if request is None:
        raise LookupError("policy request not found")
    if request.request_type != "opt_out" or request.status != "applied":
        raise ValueError("only an applied opt-out can be reversed")
    request.status = "rejected"
    request.decided_at = utcnow()
    request.decision_note = f"管理员解除永久退出：{note.strip()[:900]}"
    _restore_policy_effects(db, request.id)
    db.commit()
    return request


def _restore_policy_effects(db: Session, policy_request_id: int) -> int:
    restored = 0
    for effect in db.scalars(
        select(SourcePolicyEffect).where(
            SourcePolicyEffect.policy_request_id == policy_request_id,
            SourcePolicyEffect.reversed_at.is_(None),
        )
    ):
        intake = db.get(SourceIntake, effect.intake_id)
        if intake is None:
            continue
        intake.status = effect.previous_status
        intake.decision_note = f"管理员解除退出，恢复收录（原状态 {effect.previous_status}）\n{intake.decision_note}".strip()
        effect.reversed_at = utcnow()
        restored += 1
    return restored


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
    emergency = db.get(SourcePolicyControl, EMERGENCY_STOP_KEY) is not None
    try:
        normalized = normalize_public_https_url(source_url)
    except ValueError:
        return {"emergency_stopped": emergency, "source_status": "invalid", "allowed": False}
    now = utcnow()
    applied_opt_out = None
    active_opt_out = None
    for candidate in db.scalars(select(SourcePolicyRequest).order_by(SourcePolicyRequest.id.desc())):
        if candidate.request_type != "opt_out":
            continue
        if not _matches_source(candidate.source_url, normalized):
            continue
        if candidate.status == "applied":
            applied_opt_out = candidate
            break
        if candidate.status in ACTIVE_OPT_OUT_STATUSES - {"applied"} and active_opt_out is None:
            active_opt_out = candidate
    source_status = "active"
    if applied_opt_out is not None:
        source_status = "opted_out"
    elif active_opt_out is not None:
        expires = _hold_expires(active_opt_out)
        if expires is not None and _aware(expires, now) > now:
            source_status = "legal_hold"
    allowed = not emergency and source_status == "active"
    return {
        "emergency_stopped": emergency,
        "source_status": source_status,
        "allowed": allowed,
    }


def _hold_expires(request: SourcePolicyRequest):
    if request.temporary_hold_at is None:
        return None
    if request.status == "pending_unverified":
        return request.temporary_hold_at + timedelta(hours=UNVERIFIED_HOLD_HOURS)
    if request.status == "verified":
        return request.temporary_hold_at + timedelta(days=VERIFIED_HOLD_DAYS)
    return None
