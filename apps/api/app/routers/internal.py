from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import SourceIntake
from ..schemas import SourceIntakeClaimOut, SourceIntakeClaimRequest, SourceIntakeResult
from ..security import require_intake_worker
from ..services.source_intake import enqueue_transition_notification, utcnow

router = APIRouter(
    prefix="/api/v1/internal/source-intakes",
    tags=["internal-source-intakes"],
    dependencies=[Depends(require_intake_worker)],
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
        "attempt_count": intake.attempt_count,
        "product_count": intake.product_count,
        "lease_expires_at": intake.lease_expires_at,
        "finished_at": intake.finished_at,
    }


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
        if intake.status == "onboarded":
            return _response(intake)
        if intake.status != "validated":
            raise HTTPException(status_code=409, detail=f"cannot onboard intake in status {intake.status}")
        if not payload.published:
            raise HTTPException(status_code=409, detail="onboarded requires a successful published sync")
        if payload.attempt_count != intake.attempt_count:
            raise HTTPException(status_code=409, detail="stale intake attempt")
        if payload.product_count <= 0 and intake.product_count <= 0:
            raise HTTPException(status_code=422, detail="onboarded requires at least one product")
        intake.status = "onboarded"
        intake.product_count = max(intake.product_count, payload.product_count)
        intake.failure_reason = ""
        intake.lease_expires_at = None
        intake.finished_at = utcnow()
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_intake.onboarded",
            subject="店铺已正式收录",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已完成验证并发布。\n"
                f"已发布商品数：{intake.product_count}。"
            ),
        )
        db.commit()
        return _response(intake)

    if intake.status == payload.status and payload.status in {"no_products", "validation_failed"}:
        return _response(intake)
    if intake.status == payload.status == "validated":
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
                f"原因：{reason}\n"
                "管理员可以重新验证。"
            ),
            attempt=intake.attempt_count,
        )
    db.commit()
    return _response(intake)
