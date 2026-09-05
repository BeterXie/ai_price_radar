from __future__ import annotations

import hashlib
import re
import urllib.parse
from datetime import timedelta
from typing import Any, Sequence

from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import SourceCandidate, SourceDiscoveryRun, SourceIntake
from .source_intake import utcnow
from .source_platform import canonical_source_platform, normalize_public_https_url


DETECTED_PLATFORMS = frozenset(
    {"unknown", "ldxp", "dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "other"}
)
ORIGIN_KEY_PLATFORMS = frozenset({"dujiao_next", "woocommerce"})
PROMOTABLE_PLATFORMS = frozenset({"dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org"})
AUTO_APPROVE_SETTING = {
    "dujiao_next": "discovery_dujiao_auto_approve",
    "woocommerce": "discovery_woocommerce_auto_approve",
    "schema_org": "discovery_schema_auto_approve",
    "merchant_json": "discovery_merchant_auto_approve",
    "16688": "discovery_16688_auto_approve",
}
TERMINAL_MANUAL_STATUSES = frozenset({"rejected", "disabled"})
FAILURE_BACKOFF_HOURS = {
    "network_error": 1,
    "rate_limited": 6,
    "timeout": 2,
    "validation_failed": 24,
    "no_match": 7 * 24,
    "unsupported": 30 * 24,
}
DEFAULT_BACKOFF_HOURS = 24
MAX_SAMPLE_PRODUCTS = 5
MAX_SAMPLE_NAME_LENGTH = 200
MAX_SAMPLE_URL_LENGTH = 2000
MAX_FINGERPRINTS = 50
MAX_FINGERPRINT_LENGTH = 100
MAX_FAILURE_REASON_LENGTH = 500
MAX_DECISION_NOTE_LENGTH = 1000
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _merge_unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _utc_aware(value: Any, now: Any) -> Any:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=now.tzinfo)


def _normalized_failure_reason(value: str) -> str:
    return " ".join((value or "").split())[:MAX_FAILURE_REASON_LENGTH]


def failure_backoff_hours(reason: str) -> int:
    normalized = _normalized_failure_reason(reason).casefold()
    for marker, hours in FAILURE_BACKOFF_HOURS.items():
        if marker in normalized:
            return hours
    return DEFAULT_BACKOFF_HOURS


def normalize_candidate_url(value: object) -> str:
    normalized = normalize_public_https_url(value)
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("candidate URL contains invalid control characters")
    return normalized


def candidate_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    host = parsed.hostname or ""
    rendered_host = f"[{host}]" if ":" in host else host
    if parsed.port not in (None, 443):
        rendered_host = f"{rendered_host}:{parsed.port}"
    return urllib.parse.urlunsplit(("https", rendered_host, "", "", ""))


def candidate_key_for(normalized_url: str, platform_hint: str) -> str:
    hint = canonical_source_platform(platform_hint)
    if hint in ORIGIN_KEY_PLATFORMS:
        return candidate_origin(normalized_url)
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def _lock_identity(db: Session, candidate_key: str) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": f"source-candidate\n{candidate_key}"},
        )


def _existing_candidate(db: Session, candidate_key: str) -> SourceCandidate | None:
    return db.scalar(
        select(SourceCandidate).where(SourceCandidate.candidate_key == candidate_key)
    )


def upsert_candidate(
    db: Session,
    *,
    discovered_url: str,
    platform_hint: str = "unknown",
    discovered_by: str = "manual",
    matched_query: str = "",
    run_id: int | None = None,
) -> dict[str, object]:
    hint = canonical_source_platform(platform_hint)
    if hint not in DETECTED_PLATFORMS:
        raise ValueError("invalid platform hint")
    normalized = normalize_candidate_url(discovered_url)
    key = candidate_key_for(normalized, hint)
    origin = candidate_origin(normalized)
    now = utcnow()
    _lock_identity(db, key)
    existing = _existing_candidate(db, key)
    if existing is not None:
        merged = False
        discovery_sources = _merge_unique([*existing.discovery_sources, discovered_by])
        matched_queries = _merge_unique([*existing.matched_queries, matched_query]) if matched_query else existing.matched_queries
        if discovery_sources != existing.discovery_sources or matched_queries != existing.matched_queries:
            existing.discovery_sources = discovery_sources
            existing.matched_queries = matched_queries
            merged = True
        existing.last_seen_at = now
        if existing.status in TERMINAL_MANUAL_STATUSES:
            existing.decision_note = _trim_note(
                f"{existing.decision_note}\n再次被 {discovered_by} 发现，但保持 {existing.status}（粘性）"
            )
        elif (
            existing.status in {"validation_failed", "no_match"}
            and _utc_aware(existing.next_verify_at, now) is not None
            and _utc_aware(existing.next_verify_at, now) <= now
        ):
            existing.status = "queued"
            existing.failure_reason = ""
            existing.decision_note = _trim_note(
                f"{existing.decision_note}\n到达复验时间，重新排队"
            )
        db.flush()
        return {"candidate_id": existing.id, "is_new": False, "merged": merged}

    try:
        candidate = SourceCandidate(
            candidate_key=key,
            canonical_origin=origin,
            discovered_url=normalized,
            canonical_url=normalized,
            platform_hint=hint,
            status="discovered",
            discovery_sources=[discovered_by],
            matched_queries=[matched_query] if matched_query else [],
            first_seen_at=now,
            last_seen_at=now,
            next_verify_at=now,
            discovery_run_id=run_id,
        )
        with db.begin_nested():
            db.add(candidate)
            db.flush()
        return {"candidate_id": candidate.id, "is_new": True, "merged": False}
    except IntegrityError:
        _lock_identity(db, key)
        existing = _existing_candidate(db, key)
        if existing is None:
            raise
        existing.last_seen_at = now
        existing.discovery_sources = _merge_unique([*existing.discovery_sources, discovered_by])
        if matched_query:
            existing.matched_queries = _merge_unique([*existing.matched_queries, matched_query])
        if (
            existing.status in {"validation_failed", "no_match"}
            and _utc_aware(existing.next_verify_at, now) is not None
            and _utc_aware(existing.next_verify_at, now) <= now
        ):
            existing.status = "queued"
            existing.failure_reason = ""
        db.flush()
        return {"candidate_id": existing.id, "is_new": False, "merged": True}


def claim_candidates(
    db: Session,
    *,
    limit: int,
    lease_seconds: int,
) -> list[SourceCandidate]:
    now = utcnow()
    lease_expires_at = now + timedelta(seconds=lease_seconds)
    available = or_(
        SourceCandidate.status == "queued",
        and_(
            SourceCandidate.status == "discovered",
            SourceCandidate.next_verify_at <= now,
        ),
        and_(
            SourceCandidate.status == "validation_failed",
            SourceCandidate.next_verify_at <= now,
        ),
        and_(
            SourceCandidate.status == "no_match",
            SourceCandidate.next_verify_at <= now,
        ),
        and_(
            SourceCandidate.status == "detecting",
            or_(
                SourceCandidate.lease_expires_at.is_(None),
                SourceCandidate.lease_expires_at <= now,
            ),
        ),
    )
    rows = list(
        db.scalars(
            select(SourceCandidate)
            .where(available)
            .order_by(SourceCandidate.next_verify_at, SourceCandidate.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    for candidate in rows:
        candidate.status = "detecting"
        candidate.attempt_count += 1
        candidate.lease_expires_at = lease_expires_at
    db.commit()
    return rows


def _validate_sample_products(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(samples) > MAX_SAMPLE_PRODUCTS:
        raise ValueError(f"sample products must not exceed {MAX_SAMPLE_PRODUCTS}")
    validated: list[dict[str, Any]] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("sample products must be objects")
        name = str(sample.get("name") or "").strip()
        url = str(sample.get("url") or "").strip()
        slug = str(sample.get("product_slug") or "").strip()
        if not name or len(name) > MAX_SAMPLE_NAME_LENGTH:
            raise ValueError("sample product name is required and must be at most 200 characters")
        if not url or len(url) > MAX_SAMPLE_URL_LENGTH:
            raise ValueError("sample product url is required and must be at most 2000 characters")
        if url.startswith(("http://", "https://")):
            normalize_public_https_url(url)
        item: dict[str, Any] = {"name": name, "url": url}
        if slug:
            item["product_slug"] = slug[:200]
        validated.append(item)
    return validated


def _validate_fingerprints(values: list[str]) -> list[str]:
    if len(values) > MAX_FINGERPRINTS:
        raise ValueError(f"fingerprints must not exceed {MAX_FINGERPRINTS}")
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or len(item) > MAX_FINGERPRINT_LENGTH:
            raise ValueError("fingerprints must be non-empty and at most 100 characters")
        if item not in result:
            result.append(item)
    return result


def _trim_note(value: str) -> str:
    return "\n".join(line for line in value.splitlines() if line.strip())[:MAX_DECISION_NOTE_LENGTH]


def auto_approval_enabled(platform: str) -> bool:
    setting = AUTO_APPROVE_SETTING.get(platform)
    if setting is None:
        return False
    return bool(getattr(get_settings(), setting))


def promote_candidate_to_intake(
    db: Session,
    candidate: SourceCandidate,
    *,
    approve: bool,
) -> int | None:
    """Promote a qualified candidate to the existing Source Intake, idempotently.

    The intake approval state is decided by the caller (``approve``), never by
    re-reading the global auto-approval configuration: a candidate that did not
    satisfy the strict conditions must not be written as ``approved``.
    """
    platform = canonical_source_platform(candidate.detected_platform)
    if platform not in PROMOTABLE_PLATFORMS:
        return None
    source_url = candidate.detected_source_url or candidate.canonical_url
    source_key = candidate.detected_source_key or source_url
    _lock_identity(db, f"intake\n{platform}\n{source_key}")
    existing = db.scalar(
        select(SourceIntake).where(
            SourceIntake.source_type == platform,
            SourceIntake.source_key == source_key,
        )
    )
    if existing is not None:
        if existing.status in {"rejected", "disabled"}:
            return None
        candidate.promoted_intake_id = existing.id
        return existing.id

    now = utcnow()
    intake = SourceIntake(
        source_type=platform,
        declared_platform="auto",
        detected_platform=platform,
        source_key=source_key,
        source_url=source_url,
        shop_name=str(urllib.parse.urlsplit(source_url).hostname or ""),
        contact_email="",
        note="",
        origin="discovery",
        status="approved" if approve else "pending_review",
        decision_note=(
            "自动审批：检测契约与 AI 商品条件满足"
            if approve
            else "发现引擎合格候选，等待管理员初审"
        ),
        attempt_count=0,
        product_count=candidate.ai_product_count,
        approved_at=now if approve else None,
        finished_at=now if approve else None,
    )
    try:
        with db.begin_nested():
            db.add(intake)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SourceIntake).where(
                SourceIntake.source_type == platform,
                SourceIntake.source_key == source_key,
            )
        )
        if existing is None:
            raise
        if existing.status in {"rejected", "disabled"}:
            return None
        candidate.promoted_intake_id = existing.id
        return existing.id
    candidate.promoted_intake_id = intake.id
    return intake.id


def _update_run_stats(
    db: Session,
    candidate: SourceCandidate,
    *,
    first_verification: bool,
    detected: bool,
    ai_matched: bool,
    auto_approved: bool,
    pending_review: bool,
    validation_failed: bool,
    promoted: bool,
    platform: str,
    failure_reason: str = "",
) -> None:
    """Update the discovery run that first created this candidate.

    Counters reflect the first verification outcome of candidates newly
    discovered by that run (``discovery_run_id`` is written only on first
    insertion), so the funnel is explicitly "per run first-added candidates",
    not a global total.
    """
    if not first_verification or candidate.discovery_run_id is None:
        return
    run = db.scalar(
        select(SourceDiscoveryRun)
        .where(SourceDiscoveryRun.id == candidate.discovery_run_id)
        .with_for_update()
    )
    if run is None:
        return
    if validation_failed:
        run.validation_failed_count += 1
        category = _normalized_failure_reason(failure_reason).casefold()
        marker = next(
            (marker for marker in FAILURE_BACKOFF_HOURS if marker in category),
            "validation_failed",
        )
        failure_stats = dict(run.failure_stats or {})
        failure_stats[marker] = failure_stats.get(marker, 0) + 1
        run.failure_stats = failure_stats
        return
    run.detected_count += 1
    if platform:
        platform_stats = dict(run.platform_stats or {})
        platform_stats[platform] = platform_stats.get(platform, 0) + 1
        run.platform_stats = platform_stats
    if ai_matched:
        run.ai_matched_count += 1
    if auto_approved:
        run.auto_approved_count += 1
    if pending_review:
        run.pending_review_count += 1
    if promoted:
        run.promoted_intake_count += 1


def report_candidate_result(
    db: Session,
    *,
    candidate_id: int,
    attempt_count: int,
    status: str,
    detected_platform: str,
    detected_source_key: str,
    detected_source_url: str,
    total_product_count: int,
    ai_product_count: int,
    sample_products: list[dict[str, Any]],
    fingerprints: list[str],
    confidence_score: int,
    failure_reason: str,
) -> SourceCandidate:
    candidate = db.scalar(
        select(SourceCandidate).where(SourceCandidate.id == candidate_id).with_for_update()
    )
    if candidate is None:
        raise LookupError("candidate not found")
    if candidate.status != "detecting":
        raise ValueError(f"cannot report result from status {candidate.status}")
    if attempt_count != candidate.attempt_count:
        raise ValueError("stale detection attempt")
    now = utcnow()
    if (
        _utc_aware(candidate.lease_expires_at, now) is None
        or _utc_aware(candidate.lease_expires_at, now) <= now
    ):
        raise ValueError("detection lease expired")

    first_verification = candidate.last_verified_at is None
    candidate.lease_expires_at = None
    candidate.last_verified_at = now
    candidate.failure_reason = ""

    if status == "validation_failed":
        reason = _normalized_failure_reason(failure_reason or "source validation failed")
        candidate.status = "validation_failed"
        candidate.failure_reason = reason
        candidate.next_verify_at = now + timedelta(hours=failure_backoff_hours(reason))
        candidate.ai_product_count = 0
        candidate.sample_products = []
        candidate.fingerprints = []
        _update_run_stats(
            db,
            candidate,
            first_verification=first_verification,
            detected=False,
            ai_matched=False,
            auto_approved=False,
            pending_review=False,
            validation_failed=True,
            promoted=False,
            platform=candidate.detected_platform,
            failure_reason=reason,
        )
        db.commit()
        return candidate

    if status == "no_match":
        candidate.status = "no_match"
        candidate.failure_reason = _normalized_failure_reason(failure_reason or "no matching products")
        candidate.next_verify_at = now + timedelta(hours=7 * 24)
        candidate.ai_product_count = 0
        candidate.sample_products = []
        _update_run_stats(
            db,
            candidate,
            first_verification=first_verification,
            detected=True,
            ai_matched=False,
            auto_approved=False,
            pending_review=False,
            validation_failed=False,
            promoted=False,
            platform=candidate.detected_platform,
        )
        db.commit()
        return candidate

    if status != "detected":
        raise ValueError("invalid result status")
    platform = canonical_source_platform(detected_platform)
    if platform == "unknown":
        raise ValueError("detected platform must not be unknown")
    if platform not in DETECTED_PLATFORMS:
        raise ValueError("invalid detected platform")
    if not isinstance(total_product_count, int) or total_product_count < 0:
        raise ValueError("total_product_count must be a non-negative integer")
    if not isinstance(ai_product_count, int) or ai_product_count < 0 or ai_product_count > total_product_count:
        raise ValueError("ai_product_count must be between 0 and total_product_count")
    if not isinstance(confidence_score, int) or not 0 <= confidence_score <= 100:
        raise ValueError("confidence_score must be between 0 and 100")
    normalized_samples = _validate_sample_products(sample_products)
    normalized_fingerprints = _validate_fingerprints(fingerprints)
    normalized_source_url = normalize_candidate_url(detected_source_url or candidate.canonical_url)
    source_url = (
        candidate_origin(normalized_source_url)
        if platform in ORIGIN_KEY_PLATFORMS
        else normalized_source_url
    )
    source_key = str(detected_source_key or source_url).strip()
    if not source_key or len(source_key) > 300:
        raise ValueError("detected_source_key is required and must be at most 300 characters")
    if platform in ORIGIN_KEY_PLATFORMS:
        canonical_key = normalize_candidate_url(source_key)
        if candidate_origin(canonical_key) != source_url:
            raise ValueError("detected_source_key is not canonical for the platform")
        source_key = source_url
    elif source_key.startswith("http"):
        canonical_key = normalize_candidate_url(source_key)
        source_key = canonical_key

    candidate.detected_platform = platform
    candidate.detected_source_url = source_url
    candidate.detected_source_key = source_key
    candidate.total_product_count = total_product_count
    candidate.ai_product_count = ai_product_count
    candidate.sample_products = normalized_samples
    candidate.fingerprints = normalized_fingerprints
    candidate.confidence_score = confidence_score

    if ai_product_count <= 0:
        candidate.status = "no_match"
        candidate.failure_reason = "没有可发布的 AI 商品"
        candidate.next_verify_at = now + timedelta(hours=7 * 24)
        _update_run_stats(
            db,
            candidate,
            first_verification=first_verification,
            detected=True,
            ai_matched=False,
            auto_approved=False,
            pending_review=False,
            validation_failed=False,
            promoted=False,
            platform=platform,
        )
        db.commit()
        return candidate

    auto_approved = auto_approval_enabled(platform)
    strict_auto = (
        auto_approved
        and platform in PROMOTABLE_PLATFORMS
        and bool(normalized_samples)
        and confidence_score >= 50
    )
    if strict_auto:
        candidate.status = "auto_approved"
        candidate.decision_note = _trim_note(
            f"{candidate.decision_note}\n自动审批：{platform} 契约与 AI 商品条件满足"
        )
    else:
        candidate.status = "pending_review"
        candidate.decision_note = _trim_note(
            f"{candidate.decision_note}\n等待人工审核（自动审批关闭或条件不满足）"
        )
    candidate.next_verify_at = now + timedelta(days=30)

    promoted_intake_id: int | None = None
    if platform in PROMOTABLE_PLATFORMS:
        promoted_intake_id = promote_candidate_to_intake(
            db,
            candidate,
            approve=strict_auto,
        )
        if promoted_intake_id is not None:
            candidate.status = "promoted"
            candidate.promoted_intake_id = promoted_intake_id
            candidate.decision_note = _trim_note(
                f"{candidate.decision_note}\n已进入 Source Intake #{promoted_intake_id}"
            )
        elif candidate.status == "auto_approved":
            candidate.status = "pending_review"
            candidate.decision_note = _trim_note(
                f"{candidate.decision_note}\n已存在 rejected/disabled 的 Intake，等待管理员处理"
            )
    promoted_intake = db.get(SourceIntake, promoted_intake_id) if promoted_intake_id is not None else None
    intake_approved = promoted_intake is not None and promoted_intake.approved_at is not None
    _update_run_stats(
        db,
        candidate,
        first_verification=first_verification,
        detected=True,
        ai_matched=True,
        auto_approved=strict_auto and intake_approved,
        pending_review=not intake_approved,
        validation_failed=False,
        promoted=promoted_intake_id is not None,
        platform=platform,
    )
    db.commit()
    return candidate


def admin_retry_candidate(db: Session, candidate: SourceCandidate, *, reason: str = "") -> SourceCandidate:
    if candidate.status in {"promoted", "pending_review", "auto_approved", "detecting"}:
        raise ValueError(f"cannot retry candidate in status {candidate.status}")
    candidate.status = "queued"
    candidate.lease_expires_at = None
    candidate.failure_reason = ""
    candidate.next_verify_at = utcnow()
    candidate.decision_note = _trim_note(
        f"{candidate.decision_note}\n管理员重新排队：{_normalized_failure_reason(reason) or '无备注'}"
    )
    db.commit()
    return candidate


def admin_reject_candidate(
    db: Session,
    candidate: SourceCandidate,
    *,
    reason: str,
    disable: bool = False,
) -> SourceCandidate:
    if candidate.status in {"promoted", "detecting"}:
        raise ValueError(f"cannot {'disable' if disable else 'reject'} candidate in status {candidate.status}")
    target = "disabled" if disable else "rejected"
    candidate.status = target
    candidate.next_verify_at = None
    candidate.lease_expires_at = None
    candidate.decision_note = _trim_note(
        f"{candidate.decision_note}\n管理员{target}：{_normalized_failure_reason(reason) or '无备注'}"
    )
    db.commit()
    return candidate


def admin_promote_candidate(db: Session, candidate: SourceCandidate, *, reason: str = "") -> SourceCandidate:
    if candidate.status not in {"pending_review", "auto_approved", "detected"}:
        raise ValueError(f"cannot promote candidate in status {candidate.status}")
    platform = canonical_source_platform(candidate.detected_platform)
    if platform not in PROMOTABLE_PLATFORMS:
        raise ValueError("candidate platform is not promotable")
    if candidate.ai_product_count <= 0 or not (candidate.detected_source_url or candidate.canonical_url):
        raise ValueError("candidate must have AI products and a validated source URL")
    promoted_intake_id = promote_candidate_to_intake(db, candidate, approve=True)
    if promoted_intake_id is None:
        candidate.status = "pending_review"
        candidate.decision_note = _trim_note(
            f"{candidate.decision_note}\n管理员促进失败：已存在 rejected/disabled 的 Intake"
        )
        db.commit()
        return candidate
    candidate.status = "promoted"
    candidate.promoted_intake_id = promoted_intake_id
    candidate.decision_note = _trim_note(
        f"{candidate.decision_note}\n管理员手动促进到 Source Intake #{promoted_intake_id}：{_normalized_failure_reason(reason) or '无备注'}"
    )
    db.commit()
    return candidate


def recover_unpromoted_candidates(db: Session, *, limit: int = 100) -> int:
    """Idempotently re-promote candidates that were approved but lost their intake link."""
    rows = list(
        db.scalars(
            select(SourceCandidate)
            .where(
                SourceCandidate.status.in_({"auto_approved", "pending_review"}),
                SourceCandidate.promoted_intake_id.is_(None),
                SourceCandidate.detected_platform.in_(PROMOTABLE_PLATFORMS),
                ~select(SourceIntake.id).where(
                    SourceIntake.source_type == SourceCandidate.detected_platform,
                    SourceIntake.source_key == SourceCandidate.detected_source_key,
                    SourceIntake.status.in_(TERMINAL_MANUAL_STATUSES),
                ).exists(),
            )
            .order_by(SourceCandidate.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    recovered = 0
    for candidate in rows:
        platform = canonical_source_platform(candidate.detected_platform)
        if platform not in PROMOTABLE_PLATFORMS:
            continue
        promoted_intake_id = promote_candidate_to_intake(
            db,
            candidate,
            approve=candidate.status == "auto_approved",
        )
        if promoted_intake_id is None:
            candidate.status = "pending_review"
            candidate.decision_note = _trim_note(
                f"{candidate.decision_note}\n恢复促进失败：已存在 rejected/disabled 的 Intake"
            )
            continue
        candidate.status = "promoted"
        candidate.promoted_intake_id = promoted_intake_id
        candidate.decision_note = _trim_note(
            f"{candidate.decision_note}\n恢复任务：重新进入 Source Intake #{promoted_intake_id}"
        )
        recovered += 1
    db.commit()
    return recovered
