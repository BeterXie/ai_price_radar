from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, case, cast, delete, func, nullslast, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

RECLASSIFY_BATCH_SIZE = 200

from ..database import get_db
from ..models import (
    AdminBroadcast,
    NotificationOutbox,
    Offer,
    Product,
    RawProduct,
    Report,
    ScanRun,
    Shop,
    ShopCoupon,
    CouponCampaign,
    SourceCandidate,
    SourceDiscoveryRun,
    SourceIntake,
    SystemSetting,
    CommunitySkill,
    User,
    UserActionLog,
    UserBotBinding,
    UserProductSubscription,
    UserSession,
)
from ..schemas import (
    AdminBroadcastAudienceOut,
    AdminBroadcastCreate,
    AdminBroadcastItem,
    AdminCampaignCreate,
    AdminCouponCleanupExpiredOut,
    AdminCouponImportRequest,
    AdminCouponImportResponse,
    AdminCouponPageOut,
    AdminCouponSettingsUpdate,
    AdminCouponStats,
    AdminCouponSyncRequest,
    AdminOfferUpdate,
    AdminReportUpdate,
    AdminSettingsOut,
    AdminSettingsUpdate,
    AdminStats,
    AdminUserActionLogItem,
    AdminUserDetailOut,
    AdminUserItem,
    AdminUserPageOut,
    AdminUserSessionItem,
    AdminUserStatsOut,
    AdminUserStatusUpdate,
    CampaignRead,
    CouponRead,
    NotificationOutboxOut,
    ReportOut,
    SourceCandidateAction,
    SourceCandidateCleanupOut,
    SourceCandidateCleanupRequest,
    SourceCandidateOut,
    SourceDiscoveryRunOut,
    SourceIntakeApprove,
    SourceIntakeOut,
    SourceIntakeReject,
    SourceIntakeUpdatePlatform,
    AdminCommunitySkillCreate,
    AdminCommunitySkillUpdate,
    CommunitySkillDetailOut,
    CommunitySkillPageOut,
    CommunitySkillSummaryOut,
    UserBotBindingRead,
)
from ..security import require_admin
from ..services.classifier import classify_product
from ..services.catalog import get_current_snapshot
from ..services.community_skills import (
    admin_create_community_skill,
    admin_delete_community_skill,
    admin_toggle_community_skill_visibility,
    admin_update_community_skill,
    get_community_skill_by_slug,
    list_community_skills,
)
from ..services.source_discovery import (
    admin_promote_candidate,
    admin_reject_candidate,
    admin_retry_candidate,
    recover_unpromoted_candidates,
)
from ..services.outbox import refresh_broadcast_status
from ..services.source_intake import email_statuses, enqueue_transition_notification, site_url, utcnow
from ..services.source_platform import (
    _16688_detection,
    _ldxp_detection,
    public_https_url_or_empty,
    workflow_status,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def get_setting_bool(db: Session, key: str, default: bool = False) -> bool:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting or not setting.value:
        return default
    return setting.value.strip().lower() in ("true", "1", "yes", "on")


def set_setting_str(db: Session, key: str, value: str) -> None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


def get_setting_str(db: Session, key: str, default: str = "") -> str:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting or setting.value is None:
        return default
    return setting.value


def get_setting_int(db: Session, key: str, default: int = 0) -> int:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting or setting.value is None:
        return default
    try:
        return int(setting.value.strip())
    except (ValueError, TypeError):
        return default



@router.get("/settings", response_model=AdminSettingsOut)
def get_admin_settings(db: Session = Depends(get_db)) -> AdminSettingsOut:
    return AdminSettingsOut(
        advertise_enabled=get_setting_bool(db, "advertise_enabled", default=False),
        bot_enabled=get_setting_bool(db, "bot_enabled", default=True),
        site_notice_enabled=get_setting_bool(db, "site_notice_enabled", default=True),
        site_notice_badge=get_setting_str(db, "site_notice_badge", default="最新动态"),
        site_notice_title=get_setting_str(db, "site_notice_title", default="已支持 16688 平台商户比价与 Agent 开放快照"),
        site_notice_content=get_setting_str(db, "site_notice_content", default="我们新增了 16688 渠道 AI 商品实时抓取，并上线了面向 AI Agent 与开发者的全站静态只读 Feed。"),
        site_notice_link_text=get_setting_str(db, "site_notice_link_text", default="查看开发文档"),
        site_notice_link_url=get_setting_str(db, "site_notice_link_url", default="/developers"),
        community_enabled=get_setting_bool(db, "community_enabled", default=True),
        community_title=get_setting_str(db, "community_title", default="加入 AI 比价交流群"),
        community_desc=get_setting_str(db, "community_desc", default="第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。"),
        community_qq_group=get_setting_str(db, "community_qq_group", default="938741334"),
        community_qq_url=get_setting_str(db, "community_qq_url", default=""),
        community_btn_text=get_setting_str(db, "community_btn_text", default="一键加入 QQ 群"),
    )


@router.patch("/settings", response_model=AdminSettingsOut)
def update_admin_settings(
    payload: AdminSettingsUpdate,
    db: Session = Depends(get_db),
) -> AdminSettingsOut:
    if payload.advertise_enabled is not None:
        set_setting_str(db, "advertise_enabled", "true" if payload.advertise_enabled else "false")
    if payload.bot_enabled is not None:
        set_setting_str(db, "bot_enabled", "true" if payload.bot_enabled else "false")
    if payload.site_notice_enabled is not None:
        set_setting_str(db, "site_notice_enabled", "true" if payload.site_notice_enabled else "false")
    if payload.site_notice_badge is not None:
        set_setting_str(db, "site_notice_badge", payload.site_notice_badge.strip())
    if payload.site_notice_title is not None:
        set_setting_str(db, "site_notice_title", payload.site_notice_title.strip())
    if payload.site_notice_content is not None:
        set_setting_str(db, "site_notice_content", payload.site_notice_content.strip())
    if payload.site_notice_link_text is not None:
        set_setting_str(db, "site_notice_link_text", payload.site_notice_link_text.strip())
    if payload.site_notice_link_url is not None:
        set_setting_str(db, "site_notice_link_url", payload.site_notice_link_url.strip())
    if payload.community_enabled is not None:
        set_setting_str(db, "community_enabled", "true" if payload.community_enabled else "false")
    if payload.community_title is not None:
        set_setting_str(db, "community_title", payload.community_title.strip())
    if payload.community_desc is not None:
        set_setting_str(db, "community_desc", payload.community_desc.strip())
    if payload.community_qq_group is not None:
        set_setting_str(db, "community_qq_group", payload.community_qq_group.strip())
    if payload.community_qq_url is not None:
        set_setting_str(db, "community_qq_url", payload.community_qq_url.strip())
    if payload.community_btn_text is not None:
        set_setting_str(db, "community_btn_text", payload.community_btn_text.strip())
    db.commit()
    return get_admin_settings(db)


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
    restricted_offers = db.scalar(
        select(func.count()).select_from(Offer).where(
            or_(
                Offer.active.is_(False),
                and_(Offer.hidden_reason.is_not(None), func.trim(Offer.hidden_reason) != ""),
            )
        )
    ) or 0
    unclassified_offers = db.scalar(
        select(func.count()).select_from(Offer).where(Offer.product_id.is_(None))
    ) or 0

    current_snapshot = get_current_snapshot(db)
    public_offers_stmt = select(func.count()).select_from(Offer).where(
        Offer.active.is_(True),
        Offer.approved.is_(True),
        Offer.product_id.is_not(None),
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
    )
    product_stmt = (
        select(Product.slug, func.count(Offer.id))
        .join(Offer, Offer.product_id == Product.id)
        .where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
        )
    )
    brand_stmt = (
        select(Product.platform, func.count(Offer.id))
        .join(Offer, Offer.product_id == Product.id)
        .where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
        )
    )
    if current_snapshot is not None:
        public_offers_stmt = public_offers_stmt.where(Offer.snapshot_id == current_snapshot.id)
        product_stmt = product_stmt.where(Offer.snapshot_id == current_snapshot.id)
        brand_stmt = brand_stmt.where(Offer.snapshot_id == current_snapshot.id)

    product_counts_raw = db.execute(product_stmt.group_by(Product.slug)).all()
    product_counts = {slug: count for slug, count in product_counts_raw if slug}

    brand_counts_raw = db.execute(brand_stmt.group_by(Product.platform)).all()
    brand_counts = {brand: count for brand, count in brand_counts_raw if brand}

    total_users = db.scalar(select(func.count()).select_from(User)) or 0

    return AdminStats(
        shops=db.scalar(select(func.count()).select_from(Shop)) or 0,
        products=db.scalar(select(func.count()).select_from(Product)) or 0,
        offers=db.scalar(select(func.count()).select_from(Offer)) or 0,
        public_offers=db.scalar(public_offers_stmt) or 0,
        restricted_offers=restricted_offers,
        unclassified_offers=unclassified_offers,
        open_corrections=open_corrections,
        pending_source_intakes=pending_source_intakes,
        open_reports=open_corrections,
        total_users=total_users,
        last_scan_at=last_scan,
        product_counts=product_counts,
        brand_counts=brand_counts,
    )


@router.get("/offers")
def offers(
    approved: bool | None = None,
    active: bool | None = None,
    status: str | None = None,
    stock_status: str | None = None,
    scope: str = Query(default="current", pattern="^(current|all)$"),
    q: str | None = None,
    brand: str | None = None,
    product_slug: str | None = None,
    sort: str = Query(default="frontend", pattern="^(frontend|updated_desc|updated_asc|price_asc|price_desc)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=10000),
    response: Response = Response(),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(Offer)
        .join(Offer.shop)
        .join(Offer.raw_product)
        .outerjoin(Offer.product)
        .options(joinedload(Offer.shop), joinedload(Offer.product), joinedload(Offer.raw_product))
    )

    current_snapshot = get_current_snapshot(db)
    is_explicit_id_search = False
    if q and q.strip():
        cleaned = q.strip()
        num_str = cleaned.lstrip("#")
        if num_str.isdigit() and (cleaned.startswith("#") or cleaned.isdigit()):
            is_explicit_id_search = True

    if scope == "current" and current_snapshot is not None and not is_explicit_id_search:
        stmt = stmt.where(Offer.snapshot_id == current_snapshot.id)

    if status in ("restricted", "hidden"):
        stmt = stmt.where(
            or_(
                Offer.active.is_(False),
                and_(Offer.hidden_reason.is_not(None), func.trim(Offer.hidden_reason) != ""),
            )
        )
    elif status == "unclassified":
        stmt = stmt.where(Offer.product_id.is_(None))
    elif status == "pending":
        stmt = stmt.where(Offer.approved.is_(False))
    elif status == "active":
        stmt = stmt.where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Offer.product_id.is_not(None),
            or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
        )

    if approved is not None:
        stmt = stmt.where(Offer.approved == approved)
    if active is not None:
        stmt = stmt.where(Offer.active == active)
    if stock_status and stock_status.strip():
        stmt = stmt.where(Offer.stock_status == stock_status.strip())
    if brand:
        stmt = stmt.where(Product.platform == brand)
    if product_slug:
        stmt = stmt.where(Product.slug == product_slug)
    if q and q.strip():
        cleaned_q = q.strip()
        term = f"%{cleaned_q}%"
        or_conditions = [
            RawProduct.original_name.ilike(term),
            Shop.name.ilike(term),
            Shop.token.ilike(term),
            Offer.hidden_reason.ilike(term),
        ]
        num_part = cleaned_q.lstrip("#")
        if num_part.isdigit():
            try:
                or_conditions.append(Offer.id == int(num_part))
            except ValueError:
                pass
        stmt = stmt.where(or_(*or_conditions))

    total_count = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).offset(None).limit(None).subquery())
    ) or 0
    if response is not None:
        response.headers["X-Total-Count"] = str(total_count)

    sort_val = sort.default if hasattr(sort, "default") else str(sort or "frontend")
    if sort_val == "frontend":
        order_clauses = [
            case((Offer.stock_status == "in_stock", 0), else_=1),
            case((Offer.currency == "CNY", 0), else_=1),
            nullslast(Offer.price.asc()),
            Offer.observed_at.desc(),
            Offer.id.asc(),
        ]
    elif sort_val == "price_asc":
        order_clauses = [nullslast(Offer.price.asc()), Offer.id.asc()]
    elif sort_val == "price_desc":
        order_clauses = [nullslast(Offer.price.desc()), Offer.id.asc()]
    elif sort_val == "updated_asc":
        order_clauses = [Offer.updated_at.asc(), Offer.id.asc()]
    else:  # updated_desc
        order_clauses = [Offer.updated_at.desc(), Offer.id.asc()]

    limit_val = int(limit.default if hasattr(limit, "default") else limit)
    offset_val = int(offset.default if hasattr(offset, "default") else offset)
    stmt = stmt.order_by(*order_clauses).offset(offset_val).limit(limit_val)
    rows = list(db.scalars(stmt).unique())
    return [{
        "id": x.id,
        "shop": x.shop.name or x.shop.token,
        "shop_token": x.shop.token,
        "title": x.raw_product.original_name,
        "original_category": x.raw_product.original_category,
        "product_slug": x.product.slug if x.product else None,
        "product_name": x.product.display_name if x.product else None,
        "brand": x.product.platform if x.product else None,
        "price": str(x.price) if x.price is not None else None,
        "currency": x.currency,
        "stock_count": x.stock_count,
        "stock_status": x.stock_status,
        "approved": x.approved,
        "active": x.active,
        "hidden_reason": x.hidden_reason,
        "observed_at": x.observed_at,
        "updated_at": x.updated_at,
    } for x in rows]


@router.patch("/offers/{offer_id}")
def update_offer(offer_id: int, payload: AdminOfferUpdate, db: Session = Depends(get_db)) -> dict:
    offer = db.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer not found")
    data = payload.model_dump(exclude_unset=True)
    if "product_slug" in data:
        product_slug = data.pop("product_slug")
        tags = list(offer.tags or [])
        if "manual_override" not in tags:
            tags.append("manual_override")
        offer.tags = tags
        offer.classification_confidence = 100
        if not product_slug or str(product_slug).strip() == "":
            offer.product_id = None
        else:
            product = db.scalar(select(Product).where(Product.slug == str(product_slug).strip()))
            if product is None:
                raise HTTPException(status_code=404, detail="product not found")
            offer.product_id = product.id
    for key, value in data.items():
        setattr(offer, key, value)
    db.commit()
    return {"ok": True, "id": offer.id}


@router.post("/offers/{offer_id}/reclassify")
def reclassify_offer(offer_id: int, db: Session = Depends(get_db)) -> dict:
    offer = db.scalar(
        select(Offer)
        .options(joinedload(Offer.raw_product), joinedload(Offer.shop))
        .where(Offer.id == offer_id)
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="offer not found")
    source_platform = str(offer.shop.platform or "")
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    category_values = [offer.raw_product.original_category]
    if source_platform.strip().casefold() == "16688":
        source_category = raw_json.get("sourceCategory") or raw_json.get("source_category")
        if isinstance(source_category, dict):
            category_values.append(source_category.get("name", ""))
        elif source_category:
            category_values.append(str(source_category))
    description_values = [raw_json.get("description", "")]
    if source_platform.strip().casefold() == "16688":
        description_values.extend(raw_json.get(key, "") for key in ("content", "instruction", "remark"))
    category = " ".join(str(value or "") for value in category_values)
    description = " ".join(str(value or "") for value in description_values)
    result = classify_product(
        offer.raw_product.original_name,
        category,
        description,
        source_platform=source_platform,
    )
    target_product = (
        db.scalar(select(Product).where(Product.slug == result.slug))
        if result.slug
        else None
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
    offer.product_id = target_product.id if target_product else None
    offer.tags = [tag for tag in (offer.tags or []) if tag != "manual_override"]
    db.commit()
    return {
        "ok": True,
        "id": offer.id,
        "product_slug": result.slug,
        "confidence": result.confidence,
        "delivery_type": result.delivery_type,
    }


@router.post("/reclassify")
def reclassify(db: Session = Depends(get_db)) -> dict:
    products_by_slug = dict(db.execute(select(Product.slug, Product.id)).all())
    changed = 0
    unclassified = 0
    last_offer_id = 0
    while True:
        batch = list(
            db.scalars(
                select(Offer)
                .options(joinedload(Offer.raw_product), joinedload(Offer.shop))
                .where(Offer.id > last_offer_id)
                .order_by(Offer.id)
                .limit(RECLASSIFY_BATCH_SIZE)
            )
        )
        if not batch:
            break
        last_offer_id = batch[-1].id
        for offer in batch:
            if "manual_override" in (offer.tags or []) or (offer.classification_confidence or 0) >= 100:
                continue
            source_platform = str(offer.shop.platform or "")
            raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
            category_values = [offer.raw_product.original_category]
            if source_platform.strip().casefold() == "16688":
                source_category = raw_json.get("sourceCategory") or raw_json.get("source_category")
                if isinstance(source_category, dict):
                    category_values.append(source_category.get("name", ""))
                elif source_category:
                    category_values.append(str(source_category))
            description_values = [raw_json.get("description", "")]
            if source_platform.strip().casefold() == "16688":
                description_values.extend(raw_json.get(key, "") for key in ("content", "instruction", "remark"))
            category = " ".join(str(value or "") for value in category_values)
            description = " ".join(str(value or "") for value in description_values)
            result = classify_product(
                offer.raw_product.original_name,
                category,
                description,
                source_platform=source_platform,
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
            was_unclassified = offer.product_id is None
            target_id = products_by_slug.get(result.slug)
            if offer.product_id != target_id:
                offer.product_id = target_id
                changed += 1
            if (
                source_platform.strip().casefold() == "16688"
                and was_unclassified
                and target_id is not None
                and result.confidence >= 80
                and not offer.approved
                and offer.active
                and not str(offer.hidden_reason or "").strip()
            ):
                offer.approved = True
            if target_id is None:
                unclassified += 1
        db.commit()
    return {"ok": True, "changed": changed, "unclassified": unclassified}


@router.get("/reports", response_model=list[ReportOut])
def reports(status: str = "open", db: Session = Depends(get_db)) -> list[Report]:
    stmt = select(Report).where(Report.kind != "shop_request")
    if status and status != "all":
        stmt = stmt.where(Report.status == status)
    return list(
        db.scalars(
            stmt.order_by(Report.created_at.desc())
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
def approve_source_intake(
    intake_id: int,
    payload: SourceIntakeApprove | None = None,
    db: Session = Depends(get_db),
) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status == "pending_review":
        target_platform = payload.platform if payload else None
        if target_platform:
            intake.source_type = target_platform
            intake.detected_platform = target_platform
            if target_platform == "ldxp" and (ldxp := _ldxp_detection(intake.source_url)):
                intake.source_url = ldxp.source_url
                intake.source_key = ldxp.source_key
            elif target_platform == "16688" and (p16688 := _16688_detection(intake.source_url)):
                intake.source_url = p16688.source_url
                intake.source_key = p16688.source_key
        elif intake.source_type == "other":
            if ldxp := _ldxp_detection(intake.source_url):
                intake.source_type = "ldxp"
                intake.detected_platform = "ldxp"
                intake.source_url = ldxp.source_url
                intake.source_key = ldxp.source_key
            elif p16688 := _16688_detection(intake.source_url):
                intake.source_type = "16688"
                intake.detected_platform = "16688"
                intake.source_url = p16688.source_url
                intake.source_key = p16688.source_key

        if intake.source_type == "ldxp":
            intake.status = "queued"
            next_step = "等待链动小铺 Worker 验证"
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "acg_faka"}:
            intake.status = "approved"
            next_step = "等待下一次完整目录发布"
        elif intake.source_type == "other":
            raise HTTPException(
                status_code=409,
                detail="其他独立站请先指定具体平台类型（如链动小铺、独角数卡等）后再批准",
            )
        else:
            raise HTTPException(status_code=409, detail="来源尚未完成安全检测")
        intake.approved_at = utcnow()
        intake.decision_note = f"已通过初审，{next_step}"

        shop_page_url = ""
        if intake.source_type == "acg_faka":
            raw_target = intake.source_url.rstrip("/")
            digest = hashlib.sha256(raw_target.encode("utf-8")).hexdigest()[:24]
            shop_page_url = site_url(f"/shops/acg-faka-{digest}")
        elif intake.source_key and intake.source_type in {"ldxp", "16688"}:
            shop_page_url = site_url(f"/shops/{intake.source_key}")

        shop_page_line = f"本站收录页面：{shop_page_url}\n" if shop_page_url else ""

        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_request.approved",
            subject="店铺收录申请已通过初审",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已通过初审。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
                f"{shop_page_line}"
                f"当前状态：{next_step}；商品成功进入完整快照后才会正式收录。"
            ),
        )
        db.commit()
    elif intake.status not in {"approved", "queued", "validating", "validated", "published", "onboarded"}:
        raise HTTPException(status_code=409, detail=f"cannot approve intake in status {intake.status}")
    return _source_intake_response(db, intake)


@router.post("/source-intakes/{intake_id}/platform", response_model=SourceIntakeOut)
def update_source_intake_platform(
    intake_id: int,
    payload: SourceIntakeUpdatePlatform,
    db: Session = Depends(get_db),
) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status not in {"pending_review", "validation_failed", "no_products"}:
        raise HTTPException(status_code=409, detail=f"cannot change platform in status {intake.status}")
    platform = payload.platform
    intake.source_type = platform
    intake.detected_platform = platform
    if platform == "ldxp" and (ldxp := _ldxp_detection(intake.source_url)):
        intake.source_url = ldxp.source_url
        intake.source_key = ldxp.source_key
    elif platform == "16688" and (p16688 := _16688_detection(intake.source_url)):
        intake.source_url = p16688.source_url
        intake.source_key = p16688.source_key
    intake.decision_note = f"管理员修改平台类型为 {platform}"
    db.commit()
    return _source_intake_response(db, intake)


@router.post("/source-intakes/{intake_id}/redetect", response_model=SourceIntakeOut)
def redetect_source_intake(
    intake_id: int,
    db: Session = Depends(get_db),
) -> SourceIntakeOut:
    intake = _locked_source_intake(db, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="source intake not found")
    if intake.status not in {"pending_review", "validation_failed", "no_products"}:
        raise HTTPException(status_code=409, detail=f"cannot redetect intake in status {intake.status}")
    intake.status = "submitted"
    intake.source_type = "unknown"
    intake.lease_expires_at = None
    intake.attempt_count += 1
    intake.decision_note = "管理员触发重新识别平台"
    intake.failure_reason = ""
    db.commit()
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
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
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
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "acg_faka"}:
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
    existing = db.get(NotificationOutbox, outbox_id)
    broadcast_id = None
    if existing is not None and existing.dedupe_key.startswith("broadcast:"):
        try:
            broadcast_id = int(existing.dedupe_key.split(":", 2)[1])
        except ValueError:
            broadcast_id = None
    result = db.execute(
        update(NotificationOutbox)
        .where(NotificationOutbox.id == outbox_id, NotificationOutbox.status == "failed")
        .values(status="pending", attempt_count=0, next_attempt_at=utcnow(), last_error="", sent_at=None)
    )
    if result.rowcount == 0:
        row = db.get(NotificationOutbox, outbox_id)
        if row is None:
            raise HTTPException(status_code=404, detail="notification not found")
        raise HTTPException(status_code=409, detail=f"cannot retry notification in status {row.status}")
    if broadcast_id is not None:
        refresh_broadcast_status(db, broadcast_id)
    db.commit()
    return db.get(NotificationOutbox, outbox_id)


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
    response: Response,
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
        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            conditions.append(cast(SourceCandidate.discovery_sources, JSONB).contains([discovered_by]))
        else:
            members = func.json_each(SourceCandidate.discovery_sources).table_valued("value")
            conditions.append(select(1).select_from(members).where(members.c.value == discovered_by).exists())
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
    total = db.scalar(select(func.count()).select_from(SourceCandidate).where(and_(*conditions))) or 0
    response.headers["X-Total-Count"] = str(total)
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


CLEANUP_ALLOWED_STATUSES = frozenset({"no_match", "validation_failed", "disabled", "rejected"})


@router.post("/source-candidates/cleanup", response_model=SourceCandidateCleanupOut)
def cleanup_source_candidates(
    payload: SourceCandidateCleanupRequest | None = None,
    db: Session = Depends(get_db),
) -> SourceCandidateCleanupOut:
    requested = (
        payload.statuses
        if payload and payload.statuses
        else ["no_match", "validation_failed", "disabled"]
    )
    target_statuses = [s for s in requested if s in CLEANUP_ALLOWED_STATUSES]
    if not target_statuses:
        raise HTTPException(status_code=400, detail="no valid cleanup statuses specified")
    stmt = (
        delete(SourceCandidate)
        .where(
            SourceCandidate.status.in_(target_statuses),
            SourceCandidate.promoted_intake_id.is_(None),
        )
    )
    result = db.execute(stmt)
    db.commit()
    return SourceCandidateCleanupOut(deleted_count=result.rowcount or 0, statuses=target_statuses)


@router.post("/source-candidates/recover")
def recover_source_candidate_promotions(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    recovered = recover_unpromoted_candidates(db, limit=limit)
    return {"recovered": recovered}


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


@router.get("/skills", response_model=CommunitySkillPageOut)
def admin_get_skills(
    kind: str = Query(default="", max_length=40),
    tag: str = Query(default="", max_length=50),
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CommunitySkillPageOut:
    k = kind if isinstance(kind, str) else ""
    t = tag if isinstance(tag, str) else ""
    query_str = q if isinstance(q, str) else ""
    p = page if isinstance(page, int) else 1
    ps = page_size if isinstance(page_size, int) else 50
    return list_community_skills(
        db,
        kind=k or None,
        tag=t or None,
        search=query_str or None,
        page=p,
        page_size=ps,
        visible_only=False,
    )


@router.get("/skills/{skill_id}", response_model=CommunitySkillDetailOut)
def admin_get_skill_detail(
    skill_id: int,
    db: Session = Depends(get_db),
) -> CommunitySkillDetailOut:
    skill = db.get(CommunitySkill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    detail = get_community_skill_by_slug(
        db,
        skill.slug,
        visible_only=False,
        increment_view=False,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return detail



@router.post("/skills", response_model=CommunitySkillSummaryOut)
def admin_post_skill(
    payload: AdminCommunitySkillCreate,
    db: Session = Depends(get_db),
) -> CommunitySkill:
    # Check slug uniqueness
    existing = db.scalar(select(CommunitySkill).where(CommunitySkill.slug == payload.slug.strip()))
    if existing:
        raise HTTPException(status_code=409, detail="slug already exists")
    return admin_create_community_skill(db, payload)


@router.put("/skills/{skill_id}", response_model=CommunitySkillSummaryOut)
def admin_put_skill(
    skill_id: int,
    payload: AdminCommunitySkillUpdate,
    db: Session = Depends(get_db),
) -> CommunitySkill:
    if payload.slug:
        existing = db.scalar(
            select(CommunitySkill).where(
                CommunitySkill.slug == payload.slug.strip(),
                CommunitySkill.id != skill_id,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="slug already exists")
    skill = admin_update_community_skill(db, skill_id, payload)
    if not skill:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


@router.delete("/skills/{skill_id}")
def admin_delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
) -> dict:
    if not admin_delete_community_skill(db, skill_id):
        raise HTTPException(status_code=404, detail="skill not found")
    return {"ok": True, "id": skill_id}


@router.patch("/skills/{skill_id}/visibility", response_model=CommunitySkillSummaryOut)
def admin_toggle_skill_visibility(
    skill_id: int,
    db: Session = Depends(get_db),
) -> CommunitySkill:
    skill = admin_toggle_community_skill_visibility(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


# Merchant API token comes exclusively from the environment; never ship a
# credential as a source-code default.
DEFAULT_LDXP_TOKEN = os.getenv("LDXP_MERCHANT_TOKEN", "").strip()

_LDXP_MAX_PAGES = 100


def _fetch_ldxp_batches(token: str) -> list[dict]:
    import requests
    url = "https://api.wzyp.cn/merchantApi/SalesCoupon/list"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    page_size = 50
    all_batches: list[dict] = []
    # Walk every page so batches beyond the first page are imported too.
    for page in range(1, _LDXP_MAX_PAGES + 1):
        resp = requests.post(url, headers=headers, data=f"current={page}&pageSize={page_size}", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 1:
            break
        page_list = data.get("data", {}).get("list", []) or []
        all_batches.extend(page_list)
        if len(page_list) < page_size:
            break
    return all_batches


def _fetch_ldxp_codes(token: str, coupon_id: int) -> list[dict]:
    import requests
    url = "https://api.wzyp.cn/merchantApi/SalesCoupon/codeList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    page_size = 100
    all_codes: list[dict] = []
    # Walk every page so coupon codes beyond the first 100 are imported too.
    for page in range(1, _LDXP_MAX_PAGES + 1):
        resp = requests.post(
            url,
            headers=headers,
            data=f"coupon_id={coupon_id}&current={page}&pageSize={page_size}",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 1:
            break
        page_list = data.get("data", {}).get("list", []) or []
        all_codes.extend(page_list)
        if len(page_list) < page_size:
            break
    return all_codes


def _admin_coupon_to_read(c: ShopCoupon) -> CouponRead:
    return CouponRead(
        id=c.id,
        name=c.name,
        code=c.code,
        discount_amount=c.discount_amount,
        min_spend=c.min_spend,
        shop_id=getattr(c, "shop_id", None),
        shop_name=c.shop_name,
        shop_url=public_https_url_or_empty(c.shop_url),
        is_assigned=c.is_assigned,
        assigned_at=c.assigned_at,
        expires_at=c.expires_at,
        is_used=c.is_used,
        created_at=c.created_at,
        coupon_batch_id=getattr(c, "coupon_batch_id", 0) or 0,
        campaign_id=getattr(c, "campaign_id", None),
    )


def _admin_campaign_to_read(c: CouponCampaign) -> CampaignRead:
    return CampaignRead(
        id=c.id,
        campaign_code=c.campaign_code,
        title=c.title,
        coupon_batch_id=c.coupon_batch_id,
        shop_id=getattr(c, "shop_id", None),
        shop_url=public_https_url_or_empty(getattr(c, "shop_url", None)) or None,
        shop_name=getattr(c, "shop_name", None),
        max_per_user=c.max_per_user,
        total_quota=c.total_quota,
        claimed_count=c.claimed_count,
        is_active=c.is_active,
        expires_at=c.expires_at,
        created_at=c.created_at,
    )


def _get_coupon_stats(db: Session) -> AdminCouponStats:
    now = datetime.now(timezone.utc)
    total = db.scalar(select(func.count(ShopCoupon.id))) or 0
    assigned = db.scalar(select(func.count(ShopCoupon.id)).where(ShopCoupon.is_assigned.is_(True))) or 0
    unassigned = (
        db.scalar(
            select(func.count(ShopCoupon.id)).where(
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.is_used.is_(False),
                ShopCoupon.expires_at > now,
            )
        )
        or 0
    )
    expired_unassigned = (
        db.scalar(
            select(func.count(ShopCoupon.id)).where(
                ShopCoupon.is_assigned.is_(False),
                ShopCoupon.expires_at <= now,
            )
        )
        or 0
    )
    used = db.scalar(select(func.count(ShopCoupon.id)).where(ShopCoupon.is_used.is_(True))) or 0
    campaigns = db.scalar(select(func.count(CouponCampaign.id))) or 0

    trigger_setting_count = get_setting_int(db, "coupon_drop_trigger_count", default=0)
    log_count = (
        db.scalar(
            select(func.count(UserActionLog.id)).where(
                UserActionLog.action_type == "coupon_drop_trigger"
            )
        )
        or 0
    )
    drop_trigger_count = max(trigger_setting_count, log_count)

    return AdminCouponStats(
        total_coupons=total,
        assigned_coupons=assigned,
        unassigned_coupons=unassigned,
        used_coupons=used,
        total_campaigns=campaigns,
        drop_enabled=get_setting_bool(db, "coupon_drop_enabled", default=True),
        drop_probability=get_setting_int(db, "coupon_drop_probability", default=20),
        dynamic_drop=get_setting_bool(db, "coupon_dynamic_drop", default=True),
        daily_drop_limit=get_setting_int(db, "coupon_daily_drop_limit", default=100),
        drop_trigger_count=drop_trigger_count,
        expired_unassigned_coupons=expired_unassigned,
    )


@router.get("/coupons/stats", response_model=AdminCouponStats)
def admin_get_coupon_stats(db: Session = Depends(get_db)) -> AdminCouponStats:
    return _get_coupon_stats(db)


@router.patch("/coupons/settings", response_model=AdminCouponStats)
def admin_update_coupon_settings(
    payload: AdminCouponSettingsUpdate,
    db: Session = Depends(get_db),
) -> AdminCouponStats:
    if payload.drop_enabled is not None:
        set_setting_str(db, "coupon_drop_enabled", "true" if payload.drop_enabled else "false")
    if payload.drop_probability is not None:
        val = max(0, min(100, payload.drop_probability))
        set_setting_str(db, "coupon_drop_probability", str(val))
    if payload.dynamic_drop is not None:
        set_setting_str(db, "coupon_dynamic_drop", "true" if payload.dynamic_drop else "false")
    if payload.daily_drop_limit is not None:
        set_setting_str(db, "coupon_daily_drop_limit", str(payload.daily_drop_limit))
    db.commit()
    return _get_coupon_stats(db)


@router.get("/coupons/shops")
def admin_list_coupon_shops(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return platform shops for coupon importing and campaign binding."""
    shops = db.scalars(
        select(Shop)
        .where(Shop.is_visible.is_(True))
        .order_by(Shop.name.asc(), Shop.id.asc())
    ).all()
    return [
        {
            "id": s.id,
            "name": s.name or s.token,
            "token": s.token,
            "source_url": s.source_url,
        }
        for s in shops
    ]


@router.get("/coupons", response_model=AdminCouponPageOut)
def admin_list_coupons(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: str = Query(default="all"),
    shop_id: int | None = Query(default=None),
    search: str = Query(default=""),
    db: Session = Depends(get_db),
) -> AdminCouponPageOut:
    now = datetime.now(timezone.utc)
    page_val = page if isinstance(page, int) else 1
    page_size_val = page_size if isinstance(page_size, int) else 50
    status_val = status if isinstance(status, str) else "all"
    shop_id_val = shop_id if isinstance(shop_id, int) else None
    search_val = search.strip() if isinstance(search, str) else ""

    stmt = select(ShopCoupon)
    if status_val == "assigned":
        stmt = stmt.where(ShopCoupon.is_assigned.is_(True))
    elif status_val == "unassigned":
        stmt = stmt.where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.is_used.is_(False),
            ShopCoupon.expires_at > now,
        )
    elif status_val == "expired":
        stmt = stmt.where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.expires_at <= now,
        )
    elif status_val == "used":
        stmt = stmt.where(ShopCoupon.is_used.is_(True))

    if shop_id_val is not None:
        stmt = stmt.where(ShopCoupon.shop_id == shop_id_val)

    if search_val:
        term = f"%{search_val}%"
        stmt = stmt.where(or_(ShopCoupon.code.ilike(term), ShopCoupon.name.ilike(term), ShopCoupon.shop_name.ilike(term)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(ShopCoupon.id.desc())
        .offset((page_val - 1) * page_size_val)
        .limit(page_size_val)
    ).all()

    return AdminCouponPageOut(
        items=[_admin_coupon_to_read(c) for c in items],
        total=total,
        page=page_val,
        page_size=page_size_val,
    )


def _resolve_shop(
    db: Session,
    shop_id: int | None = None,
    shop_url: str | None = None,
    shop_name: str | None = None,
) -> tuple[int | None, str, str]:
    """Helper to match a platform shop by id, url, token, or name."""
    shop = None
    if shop_id:
        shop = db.get(Shop, shop_id)
    if not shop and shop_url:
        cleaned_url = shop_url.strip()
        shop = db.scalar(select(Shop).where(Shop.source_url == cleaned_url))
        if not shop:
            token_cand = cleaned_url.rstrip("/").split("/")[-1]
            shop = db.scalar(select(Shop).where(or_(Shop.token == token_cand, Shop.token == cleaned_url)))
    if not shop and shop_name:
        shop = db.scalar(select(Shop).where(Shop.name == shop_name.strip()))

    final_id = shop.id if shop else None
    final_name = (shop.name if shop and shop.name else (shop_name or "")).strip()
    final_url = public_https_url_or_empty(shop.source_url if shop and shop.source_url else shop_url)
    return final_id, final_name, final_url


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE wildcard characters so codes match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.post("/coupons/import", response_model=AdminCouponImportResponse)
def admin_import_coupons(
    payload: AdminCouponImportRequest,
    db: Session = Depends(get_db),
) -> AdminCouponImportResponse:
    raw_lines = payload.codes_text.replace(",", "\n").replace(";", "\n").splitlines()
    codes = [line.strip() for line in raw_lines if line.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="未检测到有效券码")

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at or (now + timedelta(days=30))

    resolved_shop_id, resolved_shop_name, resolved_shop_url = _resolve_shop(
        db,
        shop_id=payload.shop_id,
        shop_url=payload.shop_url,
        shop_name=payload.shop_name,
    )
    # Unbound coupons would fall into the site-wide pool; require a resolvable shop.
    if resolved_shop_id is None and not resolved_shop_url:
        raise HTTPException(
            status_code=400,
            detail="无法确定优惠券的店铺范围：请选择平台店铺，或提供有效的店铺链接",
        )

    # Query existing codes in set
    existing_codes = set(
        db.scalars(select(ShopCoupon.code).where(ShopCoupon.code.in_(codes))).all()
    )

    imported = 0
    skipped = 0
    seen_in_batch = set()

    for code in codes:
        if code in existing_codes or code in seen_in_batch:
            skipped += 1
            continue
        seen_in_batch.add(code)
        coupon = ShopCoupon(
            coupon_batch_id=payload.coupon_batch_id,
            name=payload.name.strip(),
            code=code,
            discount_amount=payload.discount_amount,
            min_spend=payload.min_spend,
            shop_id=resolved_shop_id,
            shop_name=resolved_shop_name or "专属店铺",
            shop_url=resolved_shop_url,
            is_assigned=False,
            expires_at=expires_at,
        )
        db.add(coupon)
        imported += 1

    db.commit()
    shop_title = resolved_shop_name or "指定店铺"
    return AdminCouponImportResponse(
        success=True,
        imported_count=imported,
        skipped_count=skipped,
        message=f"成功为【{shop_title}】导入 {imported} 张券码，跳过 {skipped} 张重复券码",
    )


@router.post("/coupons/sync-ldxp", response_model=AdminCouponImportResponse)
def admin_sync_ldxp_coupons(
    payload: AdminCouponSyncRequest,
    db: Session = Depends(get_db),
) -> AdminCouponImportResponse:
    use_token = payload.token.strip() or DEFAULT_LDXP_TOKEN
    if not use_token:
        raise HTTPException(
            status_code=400,
            detail="未配置商户令牌：请在环境变量 LDXP_MERCHANT_TOKEN 中配置，或在请求体中提供 token",
        )
    try:
        batches = _fetch_ldxp_batches(use_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"调用 LDXP 接口失败: {e}") from e

    # Auto-resolve shop for LDXP
    matched_shop = db.scalar(select(Shop).where(Shop.token == "pricememo"))
    ldxp_shop_id = matched_shop.id if matched_shop else None
    ldxp_shop_name = matched_shop.name if matched_shop else "彩头AI"
    ldxp_shop_url = matched_shop.source_url if matched_shop else "https://wzyp.cn/shop/pricememo"

    imported = 0
    skipped = 0
    reconciled_used = 0
    now = datetime.now(timezone.utc)

    for batch in batches:
        coupon_id = batch.get("id")
        name = batch.get("name", "专享优惠券")
        discount = Decimal(str(batch.get("money", 5)))
        min_spend = Decimal(str(batch.get("min_money", 0)))
        end_time = batch.get("end_time")
        if end_time:
            expires_at = datetime.fromtimestamp(int(end_time), tz=timezone.utc)
        else:
            expires_at = now + timedelta(days=90)

        codes_data = _fetch_ldxp_codes(use_token, coupon_id)
        for item in codes_data:
            code_str = str(item.get("code", "")).strip()
            if not code_str:
                continue
            existing = db.scalar(select(ShopCoupon).where(ShopCoupon.code == code_str))
            if existing:
                if item.get("status") == 1 and not existing.is_used:
                    existing.is_used = True
                    reconciled_used += 1
                if existing.shop_id is None and ldxp_shop_id:
                    existing.shop_id = ldxp_shop_id
                skipped += 1
                continue

            new_coupon = ShopCoupon(
                coupon_batch_id=coupon_id,
                name=name,
                code=code_str,
                discount_amount=discount,
                min_spend=min_spend,
                shop_id=ldxp_shop_id,
                shop_name=ldxp_shop_name,
                shop_url=ldxp_shop_url,
                is_assigned=False,
                expires_at=expires_at,
                is_used=bool(item.get("status") == 1),
            )
            db.add(new_coupon)
            imported += 1

    db.commit()
    msg = f"从链动小铺同步完成：新增 {imported} 张券码，跳过 {skipped} 张已有券码"
    if reconciled_used > 0:
        msg += f"（已自动对账核销 {reconciled_used} 张已在店铺消费的券）"
    return AdminCouponImportResponse(
        success=True,
        imported_count=imported,
        skipped_count=skipped,
        message=msg,
    )


@router.delete("/coupons/{coupon_id}")
def admin_delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
) -> dict:
    coupon = db.get(ShopCoupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    db.delete(coupon)
    db.commit()
    return {"ok": True, "id": coupon_id}


@router.post("/coupons/cleanup-expired", response_model=AdminCouponCleanupExpiredOut)
def admin_cleanup_expired_coupons(
    db: Session = Depends(get_db),
) -> AdminCouponCleanupExpiredOut:
    """Batch delete unassigned coupons that have already expired."""
    now = datetime.now(timezone.utc)
    stmt = (
        delete(ShopCoupon)
        .where(
            ShopCoupon.is_assigned.is_(False),
            ShopCoupon.expires_at <= now,
        )
        .execution_options(synchronize_session="fetch")
    )
    result = db.execute(stmt)
    db.commit()
    deleted = result.rowcount or 0
    return AdminCouponCleanupExpiredOut(
        deleted_count=deleted,
        message=f"已成功清理 {deleted} 张待领取已过期的优惠券",
    )


@router.get("/coupons/campaigns", response_model=list[CampaignRead])
def admin_list_campaigns(db: Session = Depends(get_db)) -> list[CampaignRead]:
    items = db.scalars(select(CouponCampaign).order_by(CouponCampaign.id.desc())).all()
    return [_admin_campaign_to_read(c) for c in items]


@router.post("/coupons/campaigns", response_model=CampaignRead)
def admin_create_campaign(
    payload: AdminCampaignCreate,
    db: Session = Depends(get_db),
) -> CampaignRead:
    code = payload.campaign_code.strip()
    existing = db.scalar(
        select(CouponCampaign).where(CouponCampaign.campaign_code.ilike(_escape_like(code), escape="\\"))
    )
    if existing:
        raise HTTPException(status_code=409, detail="该口令已存在")

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at or (now + timedelta(days=90))

    resolved_shop_id, resolved_shop_name, resolved_shop_url = _resolve_shop(
        db,
        shop_id=payload.shop_id,
        shop_url=payload.shop_url,
        shop_name=payload.shop_name,
    )
    # A campaign without any shop binding would silently fall back to the
    # site-wide coupon pool when redeemed; reject it instead.
    if resolved_shop_id is None and not resolved_shop_url:
        raise HTTPException(
            status_code=400,
            detail="无法确定活动的店铺范围：请选择平台店铺，或提供有效的店铺链接",
        )

    campaign = CouponCampaign(
        campaign_code=code,
        title=payload.title.strip(),
        coupon_batch_id=payload.coupon_batch_id,
        shop_id=resolved_shop_id,
        shop_name=resolved_shop_name or None,
        shop_url=resolved_shop_url or None,
        max_per_user=payload.max_per_user,
        total_quota=payload.total_quota,
        claimed_count=0,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _admin_campaign_to_read(campaign)


@router.delete("/coupons/campaigns/{campaign_id}")
def admin_delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(CouponCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动口令不存在")
    db.delete(campaign)
    db.commit()
    return {"ok": True, "id": campaign_id}


def _ensure_utc_dt(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/users/stats", response_model=AdminUserStatsOut)
def admin_get_user_stats(db: Session = Depends(get_db)) -> AdminUserStatsOut:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    fifteen_mins_ago = now - timedelta(minutes=15)

    total_users = db.scalar(select(func.count(User.id))) or 0
    active_today = db.scalar(
        select(func.count(User.id)).where(
            or_(
                User.last_login_at >= today_start,
                User.last_active_at >= today_start,
            )
        )
    ) or 0
    active_7d = db.scalar(
        select(func.count(User.id)).where(
            or_(
                User.last_login_at >= seven_days_ago,
                User.last_active_at >= seven_days_ago,
            )
        )
    ) or 0
    online_now = db.scalar(
        select(func.count(User.id)).where(User.last_active_at >= fifteen_mins_ago)
    ) or 0
    total_clicks = db.scalar(select(func.sum(User.button_click_count))) or 0
    total_coupons = db.scalar(
        select(func.count(ShopCoupon.id)).where(ShopCoupon.is_assigned.is_(True))
    ) or 0

    return AdminUserStatsOut(
        total_users=total_users,
        active_today=active_today,
        active_7d=active_7d,
        online_now=online_now,
        total_clicks=int(total_clicks),
        total_coupons_held=total_coupons,
    )


@router.get("/users", response_model=AdminUserPageOut)
def admin_list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str = Query(""),
    status: str = Query("all"),
    sort_by: str = Query("last_login"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> AdminUserPageOut:
    now = datetime.now(timezone.utc)
    fifteen_mins_ago = now - timedelta(minutes=15)
    stmt = select(User)

    if q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(term),
                User.nickname.ilike(term),
                User.last_login_ip.ilike(term),
                User.qq_openid.ilike(term),
            )
        )

    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "disabled":
        stmt = stmt.where(User.is_active.is_(False))
    elif status == "online":
        stmt = stmt.where(User.last_active_at >= fifteen_mins_ago)
    elif status == "offline":
        stmt = stmt.where(or_(User.last_active_at.is_(None), User.last_active_at < fifteen_mins_ago))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    is_desc = order.lower() != "asc"
    if sort_by == "created_at":
        stmt = stmt.order_by(User.created_at.desc() if is_desc else User.created_at.asc())
    elif sort_by == "duration":
        stmt = stmt.order_by(
            User.total_duration_seconds.desc() if is_desc else User.total_duration_seconds.asc(),
            User.id.desc(),
        )
    elif sort_by == "clicks":
        stmt = stmt.order_by(
            User.button_click_count.desc() if is_desc else User.button_click_count.asc(),
            User.id.desc(),
        )
    else:  # default last_login
        order_col = User.last_login_at.desc() if is_desc else User.last_login_at.asc()
        stmt = stmt.order_by(nullslast(order_col), User.id.desc())

    offset = (page - 1) * limit
    users = list(db.scalars(stmt.offset(offset).limit(limit)))

    # Batch compute coupon counts for users on this page
    user_ids = [u.id for u in users]
    coupons_by_user: dict[int, tuple[int, int, int]] = {}
    sessions_by_user: dict[int, UserSession] = {}

    if user_ids:
        coupon_rows = db.execute(
            select(
                ShopCoupon.assigned_user_id,
                func.count(ShopCoupon.id).label("total"),
                func.count(case((and_(ShopCoupon.is_used.is_(False), ShopCoupon.expires_at > now), 1))).label("active"),
                func.count(case((ShopCoupon.is_used.is_(True), 1))).label("used"),
            )
            .where(ShopCoupon.assigned_user_id.in_(user_ids))
            .group_by(ShopCoupon.assigned_user_id)
        ).all()
        for r in coupon_rows:
            if r[0] is not None:
                coupons_by_user[r[0]] = (r[1], r[2], r[3])

        all_sessions = list(
            db.scalars(
                select(UserSession)
                .where(UserSession.user_id.in_(user_ids))
                .order_by(UserSession.created_at.desc())
            )
        )
        for s in all_sessions:
            if s.user_id not in sessions_by_user:
                sessions_by_user[s.user_id] = s

    bindings_by_user: dict[int, UserBotBinding] = {}
    if user_ids:
        all_bindings = list(
            db.scalars(
                select(UserBotBinding)
                .where(UserBotBinding.user_id.in_(user_ids))
                .order_by(UserBotBinding.is_active.desc(), UserBotBinding.id.desc())
            )
        )
        for b in all_bindings:
            if b.user_id not in bindings_by_user:
                bindings_by_user[b.user_id] = b

    items: list[AdminUserItem] = []
    for u in users:
        c_total, c_active, c_used = coupons_by_user.get(u.id, (0, 0, 0))
        latest_session = sessions_by_user.get(u.id)

        session_dur = 0
        if latest_session:
            s_end = latest_session.last_active_at or latest_session.created_at
            session_dur = max(0, int((_ensure_utc_dt(s_end) - _ensure_utc_dt(latest_session.created_at)).total_seconds()))

        is_online = bool(u.last_active_at and _ensure_utc_dt(u.last_active_at) >= fifteen_mins_ago)
        display_ip = u.last_login_ip or (latest_session.ip_address if latest_session else "")

        binding = bindings_by_user.get(u.id)

        items.append(
            AdminUserItem(
                id=u.id,
                email=u.email,
                nickname=u.nickname or (u.email.split("@")[0] if u.email else f"用户#{u.id}"),
                avatar_url=u.avatar_url or "",
                has_qq_bound=bool(u.qq_openid),
                has_bot_bound=bool(binding and binding.is_active),
                bot_channel=binding.channel if binding else None,
                bot_target_id=binding.target_id if binding else None,
                bot_active=bool(binding.is_active) if binding else False,
                is_active=u.is_active,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
                last_login_ip=display_ip,
                last_active_at=u.last_active_at,
                session_duration_seconds=session_dur,
                total_duration_seconds=max(u.total_duration_seconds or 0, session_dur),
                is_online=is_online,
                button_click_count=u.button_click_count or 0,
                coupon_count=c_total,
                active_coupon_count=c_active,
                used_coupon_count=c_used,
            )
        )

    return AdminUserPageOut(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailOut)
def admin_get_user_detail(user_id: int, db: Session = Depends(get_db)) -> AdminUserDetailOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    now = datetime.now(timezone.utc)
    fifteen_mins_ago = now - timedelta(minutes=15)

    # Sessions
    sessions = list(
        db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at.desc())
            .limit(20)
        )
    )
    session_items: list[AdminUserSessionItem] = []
    latest_dur: int | None = None
    for s in sessions:
        s_end = s.last_active_at or s.created_at
        dur = max(0, int((_ensure_utc_dt(s_end) - _ensure_utc_dt(s.created_at)).total_seconds()))
        # 0 is a valid duration for the latest session (just logged in, no
        # heartbeat yet); only the first row may set latest_dur.
        if latest_dur is None:
            latest_dur = dur
        session_items.append(
            AdminUserSessionItem(
                token=hashlib.sha256(s.token.encode("utf-8")).hexdigest()[:8] + "...",
                ip_address=s.ip_address or "",
                user_agent=s.user_agent or "",
                created_at=s.created_at,
                last_active_at=s.last_active_at,
                duration_seconds=dur,
                is_active=_ensure_utc_dt(s.expires_at) > now,
            )
        )

    # Coupons: full aggregation for the counts (unlimited) + a capped list for display
    user_coupons = list(
        db.scalars(
            select(ShopCoupon)
            .where(ShopCoupon.assigned_user_id == user.id)
            .order_by(ShopCoupon.assigned_at.desc(), ShopCoupon.id.desc())
            .limit(50)
        )
    )
    coupon_agg = db.execute(
        select(
            func.count(ShopCoupon.id).label("total"),
            func.count(case((and_(ShopCoupon.is_used.is_(False), ShopCoupon.expires_at > now), 1))).label("active"),
            func.count(case((ShopCoupon.is_used.is_(True), 1))).label("used"),
        ).where(ShopCoupon.assigned_user_id == user.id)
    ).one()
    c_total, c_active, c_used = int(coupon_agg[0] or 0), int(coupon_agg[1] or 0), int(coupon_agg[2] or 0)

    # Action logs
    action_logs = list(
        db.scalars(
            select(UserActionLog)
            .where(UserActionLog.user_id == user.id)
            .order_by(UserActionLog.id.desc())
            .limit(50)
        )
    )
    log_items = [
        AdminUserActionLogItem(
            id=l.id,
            action_type=l.action_type,
            action_name=l.action_name,
            target_id=l.target_id,
            page=l.page,
            ip_address=l.ip_address,
            extra_data=l.extra_data or {},
            created_at=l.created_at,
        )
        for l in action_logs
    ]

    # Bot bindings
    user_bot_bindings = list(
        db.scalars(
            select(UserBotBinding)
            .where(UserBotBinding.user_id == user.id)
            .order_by(UserBotBinding.is_active.desc(), UserBotBinding.id.desc())
        )
    )
    b_first = user_bot_bindings[0] if user_bot_bindings else None

    # Subscriptions
    sub_count = db.scalar(
        select(func.count(UserProductSubscription.id)).where(UserProductSubscription.user_id == user.id)
    ) or 0

    user_item = AdminUserItem(
        id=user.id,
        email=user.email,
        nickname=user.nickname or (user.email.split("@")[0] if user.email else f"用户#{user.id}"),
        avatar_url=user.avatar_url or "",
        has_qq_bound=bool(user.qq_openid),
        has_bot_bound=bool(b_first and b_first.is_active),
        bot_channel=b_first.channel if b_first else None,
        bot_target_id=b_first.target_id if b_first else None,
        bot_active=bool(b_first.is_active) if b_first else False,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        last_login_ip=user.last_login_ip or (sessions[0].ip_address if sessions else ""),
        last_active_at=user.last_active_at,
        session_duration_seconds=latest_dur or 0,
        total_duration_seconds=max(user.total_duration_seconds or 0, latest_dur or 0),
        is_online=bool(user.last_active_at and _ensure_utc_dt(user.last_active_at) >= fifteen_mins_ago),
        button_click_count=user.button_click_count or 0,
        coupon_count=c_total,
        active_coupon_count=c_active,
        used_coupon_count=c_used,
    )

    return AdminUserDetailOut(
        user=user_item,
        sessions=session_items,
        coupons=[_admin_coupon_to_read(c) for c in user_coupons],
        action_logs=log_items,
        bot_bindings=[
            UserBotBindingRead(
                id=b.id,
                channel=b.channel,
                target_id=b.target_id,
                is_active=b.is_active,
                notify_price_drop=b.notify_price_drop,
                notify_price_hike=b.notify_price_hike,
                created_at=b.created_at,
            )
            for b in user_bot_bindings
        ],
        subscription_count=sub_count,
    )


@router.patch("/users/{user_id}/status")
def admin_toggle_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return {"id": user.id, "is_active": user.is_active}


@router.get("/broadcasts/audience", response_model=AdminBroadcastAudienceOut)
def admin_broadcast_audience(db: Session = Depends(get_db)) -> AdminBroadcastAudienceOut:
    total_users = db.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
    email_users = db.scalar(
        select(func.count(User.id))
        .where(User.is_active == True, User.email.is_not(None), User.email != "")
    ) or 0

    bot_users = db.scalar(
        select(func.count(func.distinct(UserBotBinding.user_id)))
        .join(User, User.id == UserBotBinding.user_id)
        .where(User.is_active == True, UserBotBinding.is_active == True)
    ) or 0

    reach_users = db.scalar(
        select(func.count(func.distinct(User.id)))
        .outerjoin(UserBotBinding, (UserBotBinding.user_id == User.id) & (UserBotBinding.is_active == True))
        .where(
            User.is_active == True,
            or_(
                (User.email.is_not(None)) & (User.email != ""),
                UserBotBinding.id.is_not(None),
            ),
        )
    ) or 0

    return AdminBroadcastAudienceOut(
        total_users=total_users,
        email_users=email_users,
        bot_users=bot_users,
        total_reach=reach_users,
    )


@router.post("/broadcasts", response_model=AdminBroadcastItem)
def admin_create_broadcast(
    payload: AdminBroadcastCreate,
    db: Session = Depends(get_db),
) -> AdminBroadcast:
    channels = payload.channels
    existing = db.scalar(
        select(AdminBroadcast).where(AdminBroadcast.operation_key == payload.operation_key)
    )
    if existing is not None:
        if (
            existing.title != payload.title
            or existing.content != payload.content
            or existing.channels != channels
        ):
            raise HTTPException(status_code=409, detail="operation_key already belongs to a different broadcast")
        return existing
    site_url = os.getenv("NEXT_PUBLIC_SITE_URL", "https://ai.pricememo.cn").rstrip("/")
    now = datetime.now(timezone.utc)

    broadcast = AdminBroadcast(
        operation_key=payload.operation_key,
        title=payload.title.strip(),
        content=payload.content.strip(),
        channels=channels,
        status="queued",
        created_by="admin",
        created_at=now,
    )
    db.add(broadcast)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(AdminBroadcast).where(AdminBroadcast.operation_key == payload.operation_key)
        )
        if existing is None:
            raise HTTPException(status_code=409, detail="broadcast operation conflicted") from exc
        if (
            existing.title != payload.title
            or existing.content != payload.content
            or existing.channels != channels
        ):
            raise HTTPException(status_code=409, detail="operation_key already belongs to a different broadcast") from exc
        return existing

    email_count = 0
    bot_count = 0
    target_user_ids: set[int] = set()

    if "email" in channels:
        users_with_email = list(
            db.scalars(
                select(User).where(
                    User.is_active == True,
                    User.email.is_not(None),
                    User.email != "",
                )
            )
        )
        for u in users_with_email:
            target_user_ids.add(u.id)
            dedupe_key = f"broadcast:{broadcast.id}:{u.id}:email"
            outbox_row = NotificationOutbox(
                event_type="admin_broadcast",
                recipient=u.email,
                subject=f"【PriceMemo 公告】{broadcast.title}",
                text_body=(
                    f"尊敬的 {u.nickname or '用户'}，您好！\n\n"
                    f"{broadcast.content}\n\n"
                    f"------------------------------------\n"
                    f"访问 PriceMemo 查看最新 AI 比价：{site_url}\n"
                    f"如需管理订阅或通知偏好，请登录：{site_url}/account\n\n"
                    f"—— PriceMemo 团队"
                ),
                status="pending",
                dedupe_key=dedupe_key,
                next_attempt_at=now,
                created_at=now,
            )
            db.add(outbox_row)
            target_user_ids.add(u.id)

    if "bot" in channels:
        active_bindings = list(
            db.scalars(
                select(UserBotBinding)
                .join(User, User.id == UserBotBinding.user_id)
                .where(
                    User.is_active == True,
                    UserBotBinding.is_active == True,
                    UserBotBinding.target_id != "",
                )
            )
        )
        bot_msg = (
            f"📢【PriceMemo 系统公告】\n"
            f"📌 {broadcast.title}\n"
            f"------------------------------------\n"
            f"{broadcast.content}\n"
            f"------------------------------------\n"
            f"🔗 访问官网：{site_url}"
        )
        for b in active_bindings:
            db.add(NotificationOutbox(
                event_type="admin_broadcast_bot",
                recipient=b.target_id,
                subject=broadcast.title,
                text_body=bot_msg,
                status="pending",
                dedupe_key=f"broadcast:{broadcast.id}:{b.user_id}:bot:{b.id}",
                next_attempt_at=now,
                created_at=now,
            ))
            target_user_ids.add(b.user_id)

    broadcast.target_user_count = len(target_user_ids)
    broadcast.email_sent_count = email_count
    broadcast.bot_sent_count = bot_count
    if not target_user_ids:
        broadcast.status = "sent"
    db.commit()
    db.refresh(broadcast)
    return broadcast


@router.get("/broadcasts", response_model=list[AdminBroadcastItem])
def admin_list_broadcasts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AdminBroadcast]:
    stmt = select(AdminBroadcast).order_by(AdminBroadcast.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))
