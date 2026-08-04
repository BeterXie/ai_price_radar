from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    NotificationOutbox,
    Offer,
    Product,
    Report,
    ScanRun,
    Shop,
    SourceCandidate,
    SourceDiscoveryRun,
    SourceIntake,
    SourcePolicyRequest,
)
from ..schemas import (
    AdminOfferUpdate,
    AdminReportUpdate,
    AdminStats,
    NotificationOutboxOut,
    ReportOut,
    EmergencyStopBody,
    SourceCandidateAction,
    SourceCandidateOut,
    SourceDiscoveryRunOut,
    SourcePolicyDecision,
    SourcePolicyRequestOut,
    SourceIntakeOut,
    SourceIntakeReject,
)
from ..security import require_admin
from ..services.classifier import classify_product
from ..services.source_discovery import (
    admin_promote_candidate,
    admin_reject_candidate,
    admin_retry_candidate,
    recover_unpromoted_candidates,
)
from ..services.source_intake import email_statuses, enqueue_transition_notification, utcnow
from ..services.source_policy import (
    decide_policy_request,
    emergency_stop,
    resume_collection,
    reverse_applied_opt_out,
)
from ..services.source_platform import workflow_status

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db)) -> AdminStats:
    last_scan = db.scalar(select(func.max(ScanRun.finished_at)))
    open_corrections = db.scalar(
        select(func.count()).select_from(Report).where(
            Report.status == "open", Report.kind != "shop_request"
        )
    ) or 0
    pending_source_intakes = db.scalar(
        select(func.count()).select_from(SourceIntake).where(
            SourceIntake.status == "pending_review"
        )
    ) or 0
    return AdminStats(
        shops=db.scalar(select(func.count()).select_from(Shop)) or 0,
        products=db.scalar(select(func.count()).select_from(Product)) or 0,
        offers=db.scalar(select(func.count()).select_from(Offer)) or 0,
        public_offers=db.scalar(select(func.count()).select_from(Offer).where(Offer.active.is_(True), Offer.approved.is_(True))) or 0,
        open_corrections=open_corrections,
        pending_source_intakes=pending_source_intakes,
        open_reports=open_corrections,
        last_scan_at=last_scan,
    )


@router.get("/offers")
def offers(
    approved: bool | None = None,
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(Offer)
        .options(joinedload(Offer.shop), joinedload(Offer.product), joinedload(Offer.raw_product))
        .order_by(Offer.updated_at.desc())
        .limit(limit)
    )
    if approved is not None:
        stmt = stmt.where(Offer.approved == approved)
    if active is not None:
        stmt = stmt.where(Offer.active == active)
    rows = list(db.scalars(stmt).unique())
    return [{
        "id": x.id,
        "shop": x.shop.name or x.shop.token,
        "shop_token": x.shop.token,
        "title": x.raw_product.original_name,
        "product_slug": x.product.slug if x.product else None,
        "price": str(x.price) if x.price is not None else None,
        "currency": x.currency,
        "stock_status": x.stock_status,
        "approved": x.approved,
        "active": x.active,
        "hidden_reason": x.hidden_reason,
        "observed_at": x.observed_at,
    } for x in rows]


@router.patch("/offers/{offer_id}")
def update_offer(offer_id: int, payload: AdminOfferUpdate, db: Session = Depends(get_db)) -> dict:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer not found")
    data = payload.model_dump(exclude_unset=True)
    product_slug = data.pop("product_slug", None)
    if product_slug is not None:
        product = db.scalar(select(Product).where(Product.slug == product_slug))
        if product is None:
            raise HTTPException(status_code=404, detail="product not found")
        offer.product_id = product.id
    for key, value in data.items():
        setattr(offer, key, value)
    db.commit()
    return {"ok": True, "id": offer.id}


@router.post("/reclassify")
def reclassify(db: Session = Depends(get_db)) -> dict:
    products_by_slug = {x.slug: x for x in db.scalars(select(Product))}
    offers = list(db.scalars(select(Offer).options(joinedload(Offer.raw_product))))
    changed = 0
    unclassified = 0
    for offer in offers:
        result = classify_product(
            offer.raw_product.original_name,
            offer.raw_product.original_category,
            str(offer.raw_product.raw_json.get("description", "")),
        )
        offer.tags = result.tags
        offer.risk_flags = result.risk_flags
        offer.classification_confidence = result.confidence
        offer.delivery_type = result.delivery_type
        offer.is_comparable = result.is_comparable
        offer.service_period = result.service_period
        offer.warranty = result.warranty
        offer.use_scenarios = result.use_scenarios
        offer.item_fingerprint = result.item_fingerprint
        target_id = products_by_slug[result.slug].id if result.slug in products_by_slug else None
        if offer.product_id != target_id:
            offer.product_id = target_id
            changed += 1
        if target_id is None:
            unclassified += 1
    db.commit()
    return {"ok": True, "changed": changed, "unclassified": unclassified}


@router.get("/reports", response_model=list[ReportOut])
def reports(status: str = "open", db: Session = Depends(get_db)) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .where(Report.status == status, Report.kind != "shop_request")
            .order_by(Report.created_at.desc())
        )
    )


def _source_intake_response(db: Session, intake: SourceIntake) -> SourceIntakeOut:
    return SourceIntakeOut(
        id=intake.id,
        report_id=intake.report_id,
        source_type=intake.source_type,
        declared_platform=intake.declared_platform or intake.source_type,
        detected_platform=intake.detected_platform or intake.source_type,
        workflow_status=workflow_status(intake.status),
        source_key=intake.source_key,
        source_url=intake.source_url,
        shop_name=intake.shop_name,
        contact_email=intake.contact_email,
        note=intake.note,
        origin=intake.origin,
        status=intake.status,
        decision_note=intake.decision_note,
        failure_reason=intake.failure_reason,
        attempt_count=intake.attempt_count,
        product_count=intake.product_count,
        lease_expires_at=intake.lease_expires_at,
        approved_at=intake.approved_at,
        started_at=intake.started_at,
        finished_at=intake.finished_at,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
        email_status=email_statuses(db, intake.id),
    )


def _locked_source_intake(db: Session, intake_id: int) -> SourceIntake | None:
    return db.scalar(
        select(SourceIntake)
        .where(SourceIntake.id == intake_id)
        .with_for_update()
    )


@router.get("/source-intakes", response_model=list[SourceIntakeOut])
def source_intakes(status: str | None = None, db: Session = Depends(get_db)) -> list[SourceIntakeOut]:
    stmt = select(SourceIntake).order_by(SourceIntake.created_at.desc())
    if status:
        stmt = stmt.where(SourceIntake.status == status)
    rows = list(db.scalars(stmt))
    return [_source_intake_response(db, intake) for intake in rows]


@router.post("/source-intakes/{intake_id}/approve", response_model=SourceIntakeOut)
def approve_source_intake(intake_id: int, db: Session = Depends(get_db)) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status == "pending_review":
        if intake.source_type == "ldxp":
            intake.status = "queued"
            next_step = "等待链动小铺 Worker 验证"
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "schema_org"}:
            intake.status = "approved"
            next_step = "等待下一次完整目录发布"
        elif intake.source_type == "other":
            raise HTTPException(status_code=409, detail="其他独立站仅支持人工接入，不能进入自动队列")
        else:
            raise HTTPException(status_code=409, detail="来源尚未完成安全检测")
        intake.approved_at = utcnow()
        intake.decision_note = f"已通过初审，{next_step}"
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_request.approved",
            subject="店铺收录申请已通过初审",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已通过初审。\n"
                f"当前状态：{next_step}；商品成功进入完整快照后才会正式收录。"
            ),
        )
        db.commit()
    elif intake.status not in {"approved", "queued", "validating", "validated", "published", "onboarded"}:
        raise HTTPException(status_code=409, detail=f"cannot approve intake in status {intake.status}")
    return _source_intake_response(db, intake)


@router.post("/source-intakes/{intake_id}/reject", response_model=SourceIntakeOut)
def reject_source_intake(
    intake_id: int,
    payload: SourceIntakeReject,
    db: Session = Depends(get_db),
) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status == "pending_review":
        now = utcnow()
        intake.status = "rejected"
        intake.decision_note = payload.reason
        intake.finished_at = now
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_request.rejected",
            subject="店铺收录申请未通过",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）未通过初审。\n"
                f"原因：{payload.reason}"
            ),
        )
        db.commit()
    elif intake.status != "rejected":
        raise HTTPException(status_code=409, detail=f"cannot reject intake in status {intake.status}")
    return _source_intake_response(db, intake)


@router.post("/source-intakes/{intake_id}/retry", response_model=SourceIntakeOut)
def retry_source_intake(intake_id: int, db: Session = Depends(get_db)) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status in {"no_products", "validation_failed"}:
        if intake.source_type == "unknown":
            intake.status = "submitted"
            decision_note = "已重新排队，等待安全检测"
        elif intake.source_type == "ldxp":
            intake.status = "queued"
            decision_note = "已重新排队，等待链动小铺 Worker 验证"
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "schema_org"}:
            intake.status = "approved" if intake.approved_at is not None else "pending_review"
            decision_note = (
                "已恢复，等待下一次完整目录发布"
                if intake.status == "approved"
                else "已恢复，等待管理员初审"
            )
        else:
            raise HTTPException(status_code=409, detail="其他独立站仅支持人工接入，不能进入自动队列")
        intake.lease_expires_at = None
        intake.finished_at = None
        intake.decision_note = decision_note
        db.commit()
    elif intake.status not in {
        "submitted",
        "pending_review",
        "approved",
        "queued",
        "validating",
        "validated",
        "published",
        "onboarded",
    }:
        raise HTTPException(status_code=409, detail=f"cannot retry intake in status {intake.status}")
    return _source_intake_response(db, intake)


@router.post("/source-intakes/{intake_id}/notifications/retry", response_model=SourceIntakeOut)
def retry_failed_intake_notifications(intake_id: int, db: Session = Depends(get_db)) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    failed_rows = list(
        db.scalars(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == "failed",
                NotificationOutbox.dedupe_key.like(f"source-intake:{intake_id}:%"),
            )
            .with_for_update()
        )
    )
    now = utcnow()
    for row in failed_rows:
        row.status = "pending"
        row.attempt_count = 0
        row.next_attempt_at = now
        row.last_error = ""
        row.sent_at = None
    db.commit()
    return _source_intake_response(db, intake)


@router.post("/notification-outbox/{outbox_id}/retry", response_model=NotificationOutboxOut)
def retry_notification(outbox_id: int, db: Session = Depends(get_db)) -> NotificationOutbox:
    row = db.get(NotificationOutbox, outbox_id)
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.status != "sent":
        row.status = "pending"
        row.attempt_count = 0
        row.next_attempt_at = utcnow()
        row.last_error = ""
        row.sent_at = None
        db.commit()
    return row


@router.get("/source-discovery/runs", response_model=list[SourceDiscoveryRunOut])
def discovery_runs(
    status: str | None = None,
    trigger: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SourceDiscoveryRun]:
    stmt = select(SourceDiscoveryRun).order_by(SourceDiscoveryRun.id.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(SourceDiscoveryRun.status == status)
    if trigger:
        stmt = stmt.where(SourceDiscoveryRun.trigger == trigger)
    return list(db.scalars(stmt))


@router.get("/source-discovery/runs/{run_id}", response_model=SourceDiscoveryRunOut)
def discovery_run_detail(run_id: int, db: Session = Depends(get_db)) -> SourceDiscoveryRun:
    run = db.get(SourceDiscoveryRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="discovery run not found")
    return run


@router.get("/source-candidates", response_model=list[SourceCandidateOut])
def source_candidates(
    status: str | None = None,
    detected_platform: str | None = None,
    discovered_by: str | None = None,
    ai_hit: bool | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    failure_reason: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SourceCandidate]:
    conditions = []
    if status:
        conditions.append(SourceCandidate.status == status)
    if detected_platform:
        conditions.append(SourceCandidate.detected_platform == detected_platform)
    if discovered_by:
        conditions.append(SourceCandidate.discovery_sources.contains([discovered_by]))
    if ai_hit is not None:
        conditions.append(
            SourceCandidate.ai_product_count > 0 if ai_hit else SourceCandidate.ai_product_count == 0
        )
    if created_after:
        conditions.append(SourceCandidate.created_at >= created_after)
    if created_before:
        conditions.append(SourceCandidate.created_at <= created_before)
    if failure_reason:
        conditions.append(SourceCandidate.failure_reason.ilike(f"%{failure_reason}%"))
    stmt = (
        select(SourceCandidate)
        .where(and_(*conditions))
        .order_by(SourceCandidate.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.get("/source-candidates/{candidate_id}", response_model=SourceCandidateOut)
def source_candidate_detail(candidate_id: int, db: Session = Depends(get_db)) -> SourceCandidate:
    candidate = db.get(SourceCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="source candidate not found")
    return candidate


def _locked_candidate(db: Session, candidate_id: int) -> SourceCandidate:
    candidate = db.scalar(
        select(SourceCandidate).where(SourceCandidate.id == candidate_id).with_for_update()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="source candidate not found")
    return candidate


def _candidate_action(candidate_id: int, payload: SourceCandidateAction, action: str, db: Session) -> SourceCandidate:
    candidate = _locked_candidate(db, candidate_id)
    try:
        if action == "retry":
            return admin_retry_candidate(db, candidate, reason=payload.reason)
        if action == "reject":
            return admin_reject_candidate(db, candidate, reason=payload.reason)
        if action == "disable":
            return admin_reject_candidate(db, candidate, reason=payload.reason, disable=True)
        if action == "promote":
            return admin_promote_candidate(db, candidate, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="unknown candidate action")


@router.post("/source-candidates/recover")
def recover_source_candidate_promotions(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    recovered = recover_unpromoted_candidates(db, limit=limit)
    return {"recovered": recovered}


@router.get("/source-policy/requests", response_model=list[SourcePolicyRequestOut])
def source_policy_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[SourcePolicyRequest]:
    stmt = select(SourcePolicyRequest).order_by(SourcePolicyRequest.id.desc())
    if status:
        stmt = stmt.where(SourcePolicyRequest.status == status)
    return list(db.scalars(stmt))


@router.post("/source-policy/requests/{request_id}/decide", response_model=SourcePolicyRequestOut)
def decide_source_policy_request(
    request_id: int,
    payload: SourcePolicyDecision,
    db: Session = Depends(get_db),
) -> SourcePolicyRequest:
    try:
        return decide_policy_request(
            db,
            request_id,
            decision=payload.decision,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/source-policy/requests/{request_id}/reverse", response_model=SourcePolicyRequestOut)
def reverse_source_policy_request(
    request_id: int,
    payload: SourcePolicyDecision,
    db: Session = Depends(get_db),
) -> SourcePolicyRequest:
    try:
        return reverse_applied_opt_out(db, request_id, note=payload.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/source-policy/emergency-stop")
def emergency_stop_collection(
    payload: EmergencyStopBody,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    emergency_stop(db, reason=payload.reason)
    return {"emergency_stopped": True}


@router.post("/source-policy/resume")
def resume_source_collection(
    payload: EmergencyStopBody,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    resume_collection(db, note=payload.reason)
    return {"emergency_stopped": False}


@router.post("/source-candidates/{candidate_id}/retry", response_model=SourceCandidateOut)
def retry_source_candidate(
    candidate_id: int,
    payload: SourceCandidateAction,
    db: Session = Depends(get_db),
) -> SourceCandidate:
    return _candidate_action(candidate_id, payload, "retry", db)


@router.post("/source-candidates/{candidate_id}/reject", response_model=SourceCandidateOut)
def reject_source_candidate(
    candidate_id: int,
    payload: SourceCandidateAction,
    db: Session = Depends(get_db),
) -> SourceCandidate:
    return _candidate_action(candidate_id, payload, "reject", db)


@router.post("/source-candidates/{candidate_id}/disable", response_model=SourceCandidateOut)
def disable_source_candidate(
    candidate_id: int,
    payload: SourceCandidateAction,
    db: Session = Depends(get_db),
) -> SourceCandidate:
    return _candidate_action(candidate_id, payload, "disable", db)


@router.post("/source-candidates/{candidate_id}/promote", response_model=SourceCandidateOut)
def promote_source_candidate(
    candidate_id: int,
    payload: SourceCandidateAction,
    db: Session = Depends(get_db),
) -> SourceCandidate:
    return _candidate_action(candidate_id, payload, "promote", db)


@router.patch("/reports/{report_id}")
def update_report(report_id: int, payload: AdminReportUpdate, db: Session = Depends(get_db)) -> dict:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    if report.kind == "shop_request":
        raise HTTPException(status_code=409, detail="use source-intakes endpoints for shop applications")
    data = payload.model_dump(exclude_unset=True)
    report.status = data.pop("status")
    for key, value in data.items():
        if value is not None:
            setattr(report, key, value.strip())
    report.resolved_at = datetime.now(timezone.utc) if report.status == "resolved" else None
    db.commit()
    return {
        "ok": True,
        "id": report.id,
        "status": report.status,
        "public_summary": report.public_summary,
        "merchant_response": report.merchant_response,
    }
