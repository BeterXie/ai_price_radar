from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import Shop, SourceIntake
from ..schemas import (
    SourceDetectionClaimOut,
    SourceDetectionClaimRequest,
    SourceDetectionResult,
    SourceIntakeClaimOut,
    SourceIntakeClaimRequest,
    SourceIntakeResult,
)
from ..security import require_detector_worker, require_intake_worker
from ..services.source_intake import (
    enqueue_admin_notification,
    enqueue_transition_notification,
    site_url,
    utcnow,
)
from ..services.source_platform import canonical_source_platform, prepare_source_submission, workflow_status

router = APIRouter(
    prefix="/api/v1/internal/source-intakes",
    tags=["internal-source-intakes"],
    dependencies=[Depends(require_intake_worker)],
)

detector_router = APIRouter(
    prefix="/api/v1/internal/source-detections",
    tags=["internal-source-detections"],
    dependencies=[Depends(require_detector_worker)],
)

PUBLIC_VALIDATION_FAILURE_REASONS = {
    "validation_failed": "来源验证暂时失败",
}


def _is_expired(value, now) -> bool:
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=now.tzinfo)
    return value <= now


def _response(intake: SourceIntake) -> dict[str, object]:
    return {
        "intake_id": intake.id,
        "status": intake.status,
        "workflow_status": workflow_status(intake.status),
        "attempt_count": intake.attempt_count,
        "product_count": intake.product_count,
        "lease_expires_at": intake.lease_expires_at,
        "finished_at": intake.finished_at,
    }


def _joined_text(*values: object) -> str:
    return "\n".join(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))


def _merge_detected_intake(
    db: Session,
    *,
    existing: SourceIntake,
    duplicate: SourceIntake,
    platform: str,
    source_url: str,
    source_key: str,
    shop_name: str,
    product_count: int,
) -> SourceIntake:
    duplicate_email_note = ""
    if duplicate.contact_email and existing.contact_email and duplicate.contact_email != existing.contact_email:
        duplicate_email_note = f"重复申请联系邮箱：{duplicate.contact_email}"
    report_id = existing.report_id or duplicate.report_id
    if report_id == duplicate.report_id and duplicate.report_id is not None:
        duplicate.report_id = None
        db.flush()
    existing.report_id = report_id
    existing.declared_platform = (
        duplicate.declared_platform
        if existing.declared_platform == "auto" and duplicate.declared_platform != "auto"
        else existing.declared_platform
    )
    existing.detected_platform = platform
    existing.source_url = source_url
    existing.source_key = source_key
    existing.shop_name = existing.shop_name or shop_name or duplicate.shop_name
    existing.contact_email = existing.contact_email or duplicate.contact_email
    existing.note = _joined_text(existing.note, duplicate.note, duplicate_email_note)
    existing.decision_note = _joined_text(
        existing.decision_note,
        duplicate.decision_note,
        f"已合并重复收录申请 #{duplicate.id}",
    )
    existing.failure_reason = _joined_text(existing.failure_reason, duplicate.failure_reason)
    existing.origin = "manual" if "manual" in {existing.origin, duplicate.origin} else existing.origin
    existing.product_count = max(existing.product_count, duplicate.product_count, product_count)
    existing.created_at = min(existing.created_at, duplicate.created_at)
    existing.updated_at = utcnow()
    if existing.status in {"submitted", "detecting"}:
        existing.status = "pending_review"
        existing.lease_expires_at = None
        existing.finished_at = utcnow()
    db.delete(duplicate)
    return existing


def _canonical_intake(
    db: Session,
    *,
    intake_id: int,
    platform: str,
    source_key: str,
) -> SourceIntake | None:
    return db.scalar(
        select(SourceIntake)
        .where(
            SourceIntake.id != intake_id,
            SourceIntake.source_type == platform,
            SourceIntake.source_key == source_key,
        )
        .order_by(SourceIntake.id)
        .with_for_update()
        .limit(1)
    )


def _lock_canonical_identity(db: Session, platform: str, source_key: str) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
            {"identity": f"{platform}\n{source_key}"},
        )


@detector_router.post("/claim", response_model=list[SourceDetectionClaimOut])
def claim_source_detections(
    payload: SourceDetectionClaimRequest,
    db: Session = Depends(get_db),
) -> list[SourceDetectionClaimOut]:
    now = utcnow()
    lease_expires_at = now + timedelta(seconds=payload.lease_seconds)
    available = or_(
        SourceIntake.status == "submitted",
        and_(
            SourceIntake.status == "detecting",
            or_(SourceIntake.lease_expires_at.is_(None), SourceIntake.lease_expires_at <= now),
        ),
    )
    rows = list(
        db.scalars(
            select(SourceIntake)
            .where(SourceIntake.source_type == "unknown", available)
            .order_by(SourceIntake.created_at, SourceIntake.id)
            .with_for_update(skip_locked=True)
            .limit(payload.limit)
        )
    )
    for intake in rows:
        intake.status = "detecting"
        intake.attempt_count += 1
        intake.started_at = now
        intake.lease_expires_at = lease_expires_at
    db.commit()
    return [
        SourceDetectionClaimOut(
            intake_id=intake.id,
            source_url=intake.source_url,
            declared_platform=intake.declared_platform,
            attempt_count=intake.attempt_count,
            lease_expires_at=intake.lease_expires_at,
        )
        for intake in rows
    ]


@detector_router.post("/{intake_id}/result")
def report_source_detection_result(
    intake_id: int,
    payload: SourceDetectionResult,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    intake = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id).with_for_update())
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status != "detecting" or intake.source_type != "unknown":
        raise HTTPException(status_code=409, detail=f"cannot report detection from status {intake.status}")
    if payload.attempt_count != intake.attempt_count:
        raise HTTPException(status_code=409, detail="stale detection attempt")
    if _is_expired(intake.lease_expires_at, utcnow()):
        raise HTTPException(status_code=409, detail="detection lease expired")

    intake.lease_expires_at = None
    intake.finished_at = utcnow()
    if payload.status == "validation_failed":
        intake.status = "validation_failed"
        intake.failure_reason = "来源安全检测失败"
        db.commit()
        return _response(intake)

    platform = canonical_source_platform(payload.detected_platform)
    if platform not in {"ldxp", "dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "other"}:
        raise HTTPException(status_code=422, detail="invalid detected source platform")
    try:
        normalized = prepare_source_submission(payload.source_url or intake.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    source_key = normalized.source_key
    reported_source_key = payload.source_key.strip()
    if reported_source_key:
        if platform == "ldxp":
            canonical_reported_key = reported_source_key.casefold()
        else:
            try:
                canonical_reported_key = prepare_source_submission(reported_source_key).source_key
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="detector returned an invalid source key") from exc
        if canonical_reported_key != source_key:
            raise HTTPException(status_code=422, detail="detector returned a non-canonical source key")
    _lock_canonical_identity(db, platform, source_key)
    existing = _canonical_intake(db, intake_id=intake.id, platform=platform, source_key=source_key)
    if existing is not None:
        merged = _merge_detected_intake(
            db,
            existing=existing,
            duplicate=intake,
            platform=platform,
            source_url=normalized.source_url,
            source_key=source_key,
            shop_name=payload.shop_name.strip(),
            product_count=payload.product_count,
        )
        _apply_intake_approval_and_notifications(db, merged, platform, settings=get_settings())
        db.commit()
        return _response(merged)

    intake.source_type = platform
    intake.detected_platform = platform
    intake.source_url = normalized.source_url
    intake.source_key = source_key
    if payload.shop_name.strip():
        intake.shop_name = payload.shop_name.strip()
    intake.product_count = payload.product_count
    intake.failure_reason = ""
    try:
        _apply_intake_approval_and_notifications(db, intake, platform, settings=get_settings())
        db.commit()
        return _response(intake)
    except IntegrityError:
        db.rollback()

    _lock_canonical_identity(db, platform, source_key)
    duplicate = db.scalar(select(SourceIntake).where(SourceIntake.id == intake_id).with_for_update())
    existing = _canonical_intake(db, intake_id=intake_id, platform=platform, source_key=source_key)
    if duplicate is None or existing is None:
        raise HTTPException(status_code=409, detail="concurrent source normalization conflict; retry detection result")
    if (
        duplicate.status != "detecting"
        or duplicate.source_type != "unknown"
        or duplicate.attempt_count != payload.attempt_count
        or _is_expired(duplicate.lease_expires_at, utcnow())
    ):
        raise HTTPException(status_code=409, detail="stale detection attempt")
    merged = _merge_detected_intake(
        db,
        existing=existing,
        duplicate=duplicate,
        platform=platform,
        source_url=normalized.source_url,
        source_key=source_key,
        shop_name=payload.shop_name.strip(),
        product_count=payload.product_count,
    )
    _apply_intake_approval_and_notifications(db, merged, platform, settings=get_settings())
    db.commit()
    return _response(merged)


def _apply_intake_approval_and_notifications(
    db: Session,
    intake: SourceIntake,
    platform: str,
    *,
    settings: Any,
) -> None:
    if intake.status not in {"submitted", "detecting", "pending_review"}:
        return
    is_auto_approvable = (
        bool(settings.shop_intake_auto_approve)
        and platform in {"ldxp", "dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org"}
    )
    if is_auto_approvable:
        now = utcnow()
        intake.approved_at = now
        if platform == "ldxp":
            intake.status = "queued"
            next_step = "等待链动小铺 Worker 验证"
        else:
            intake.status = "approved"
            next_step = "等待下一次完整目录发布"
        intake.decision_note = f"已自动通过初审，{next_step}"
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_request.approved",
            subject="店铺收录申请已自动通过初审",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已通过安全检测并自动通过初审。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
                f"来源类型：{intake.source_type}\n"
                f"当前状态：{next_step}；商品成功进入完整快照后才会正式收录。"
            ),
        )
        enqueue_admin_notification(
            db,
            intake,
            event_type="shop_request.auto_approved.admin",
            subject=f"【自动审批通过】店铺收录已自动批准：{intake.shop_name or intake.source_key}（#{intake.id}）",
            text_body=(
                f"店铺收录申请（#{intake.id}）已通过安全检测并自动通过初审。\n"
                f"来源类型：{intake.source_type}\n"
                f"来源地址：{intake.source_url}\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"联系邮箱：{intake.contact_email}\n"
                f"当前状态：{next_step}；商品成功进入完整快照后将自动公开。\n"
                f"审批管理：{site_url(f'/admin?intake={intake.id}#source-intake-{intake.id}')}\n"
            ),
        )
    else:
        intake.status = "pending_review"



@router.post("/claim", response_model=list[SourceIntakeClaimOut])
def claim_source_intakes(
    payload: SourceIntakeClaimRequest,
    db: Session = Depends(get_db),
) -> list[SourceIntakeClaimOut]:
    now = utcnow()
    settings = get_settings()
    lease_seconds = payload.lease_seconds or settings.intake_lease_seconds
    lease_expires_at = now + timedelta(seconds=lease_seconds)
    available = or_(
        SourceIntake.status == "queued",
        and_(
            SourceIntake.status == "validating",
            or_(
                SourceIntake.lease_expires_at.is_(None),
                SourceIntake.lease_expires_at <= now,
            ),
        ),
    )
    rows = list(
        db.scalars(
            select(SourceIntake)
            .where(SourceIntake.source_type == "ldxp", available)
            .order_by(SourceIntake.created_at, SourceIntake.id)
            .with_for_update(skip_locked=True)
            .limit(payload.limit)
        )
    )
    for intake in rows:
        intake.status = "validating"
        intake.attempt_count += 1
        intake.started_at = now
        intake.lease_expires_at = lease_expires_at
    db.commit()
    return [
        SourceIntakeClaimOut(
            intake_id=intake.id,
            source_type="ldxp",
            source_key=intake.source_key,
            source_url=intake.source_url,
            shop_name=intake.shop_name,
            attempt_count=intake.attempt_count,
            lease_expires_at=intake.lease_expires_at,
        )
        for intake in rows
    ]


@router.post("/{intake_id}/result")
def report_source_intake_result(
    intake_id: int,
    payload: SourceIntakeResult,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    intake = db.scalar(
        select(SourceIntake).where(SourceIntake.id == intake_id).with_for_update()
    )
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.source_type != "ldxp":
        raise HTTPException(status_code=409, detail="merchant feed is not handled by the LDXP worker")

    if payload.status == "onboarded":
        if payload.attempt_count != intake.attempt_count:
            raise HTTPException(status_code=409, detail="stale intake attempt")
        if intake.status == "onboarded":
            return _response(intake)
        if intake.status != "validated":
            raise HTTPException(status_code=409, detail=f"cannot onboard intake in status {intake.status}")
        if not payload.published:
            raise HTTPException(status_code=409, detail="onboarded requires a successful published sync")
        if payload.product_count <= 0 and intake.product_count <= 0:
            raise HTTPException(status_code=422, detail="onboarded requires at least one product")
        intake.status = "onboarded"
        intake.product_count = max(intake.product_count, payload.product_count)
        intake.failure_reason = ""
        intake.lease_expires_at = None
        intake.finished_at = utcnow()
        shop_token = db.scalar(
            select(Shop.token)
            .where(func.lower(Shop.token) == intake.source_key.casefold())
            .order_by(Shop.id)
            .limit(1)
        ) or intake.source_key
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_intake.onboarded",
            subject="店铺已正式收录",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已完成验证并发布。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
                f"已发布商品数：{intake.product_count}。\n"
                f"本站收录页面：{site_url(f'/shops/{shop_token}')}"
            ),
        )
        db.commit()
        return _response(intake)

    # The browser worker can retry its result after the API committed it. A closed
    # attempt must not be reopened or produce a false 409, but a newer attempt remains strict.
    if (
        payload.status in {"validated", "no_products", "validation_failed"}
        and intake.status in {"validated", "no_products", "validation_failed", "onboarded"}
        and payload.attempt_count == intake.attempt_count
    ):
        return _response(intake)
    if intake.status != "validating":
        raise HTTPException(status_code=409, detail=f"cannot report result from status {intake.status}")
    if payload.attempt_count != intake.attempt_count:
        raise HTTPException(status_code=409, detail="stale intake attempt")
    if _is_expired(intake.lease_expires_at, utcnow()):
        raise HTTPException(status_code=409, detail="intake lease expired")
    if payload.status == "validated" and payload.product_count <= 0:
        raise HTTPException(status_code=422, detail="validated requires at least one product")

    intake.status = payload.status
    intake.product_count = payload.product_count
    intake.failure_reason = (
        PUBLIC_VALIDATION_FAILURE_REASONS.get(payload.status, "来源验证失败")
        if payload.status == "validation_failed"
        else ""
    )
    intake.lease_expires_at = None
    intake.finished_at = utcnow()
    if payload.status == "no_products":
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_intake.no_products",
            subject="店铺验证完成，但暂未发现目标商品",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已完成读取，但暂未发现目录范围内商品。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
                "管理员可以重新验证，或补充公开商品后再次提交。"
            ),
            attempt=intake.attempt_count,
        )
    elif payload.status == "validation_failed":
        reason = intake.failure_reason or "系统暂时无法完成来源验证"
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_intake.validation_failed",
            subject="店铺验证未完成",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）本次验证未完成。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
                f"原因：{reason}\n"
                "管理员可以重新验证。"
            ),
            attempt=intake.attempt_count,
        )
    db.commit()
    return _response(intake)
