from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, case, cast, delete, func, nullslast, or_, select, update
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
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
)
from ..schemas import (
    AdminCampaignCreate,
    AdminCouponImportRequest,
    AdminCouponImportResponse,
    AdminCouponPageOut,
    AdminCouponSettingsUpdate,
    AdminCouponStats,
    AdminOfferUpdate,
    AdminReportUpdate,
    AdminSettingsOut,
    AdminSettingsUpdate,
    AdminStats,
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
)
from ..security import require_admin
from ..services.classifier import classify_product
from ..services.catalog import get_current_snapshot
from ..services.community_skills import (
    admin_create_community_skill,
    admin_delete_community_skill,
    admin_toggle_community_skill_visibility,
    admin_update_community_skill,
    list_community_skills,
)
from ..services.source_discovery import (
    admin_promote_candidate,
    admin_reject_candidate,
    admin_retry_candidate,
    recover_unpromoted_candidates,
)
from ..services.source_intake import email_statuses, enqueue_transition_notification, utcnow
from ..services.source_platform import _16688_detection, _ldxp_detection, prepare_source_submission, workflow_status

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
    db.commit()


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
    offset: int = Query(default=0, ge=0),
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
        if not product_slug or str(product_slug).strip() == "":
            offer.product_id = None
        else:
            product = db.scalar(select(Product).where(Product.slug == str(product_slug).strip()))
            if product is None:
                raise HTTPException(status_code=404, detail="product not found")
            offer.product_id = product.id
            tags = list(offer.tags or [])
            if "manual_override" not in tags:
                tags.append("manual_override")
            offer.tags = tags
            offer.classification_confidence = 100
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
    products_by_slug = {x.slug: x for x in db.scalars(select(Product))}
    offers = list(db.scalars(select(Offer).options(joinedload(Offer.raw_product), joinedload(Offer.shop))))
    changed = 0
    unclassified = 0
    for offer in offers:
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
        target_id = products_by_slug[result.slug].id if result.slug in products_by_slug else None
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
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org"}:
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
        enqueue_transition_notification(
            db,
            intake,
            event_type="shop_request.approved",
            subject="店铺收录申请已通过初审",
            text_body=(
                f"你的店铺收录申请（#{intake.id}）已通过初审。\n"
                f"店铺名称：{intake.shop_name or '未填写'}\n"
                f"店铺地址：{intake.source_url}\n"
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
        elif intake.source_type in {"dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org"}:
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


DEFAULT_LDXP_TOKEN = "182d5854-1b08-4c93-aa06-33189b3971a3"


def _fetch_ldxp_batches(token: str) -> list[dict]:
    import requests
    url = "https://api.wzyp.cn/merchantApi/SalesCoupon/list"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(url, headers=headers, data="current=1&pageSize=50", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("list", []) if data.get("code") == 1 else []


def _fetch_ldxp_codes(token: str, coupon_id: int) -> list[dict]:
    import requests
    url = "https://api.wzyp.cn/merchantApi/SalesCoupon/codeList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(url, headers=headers, data=f"coupon_id={coupon_id}&current=1&pageSize=100", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("list", []) if data.get("code") == 1 else []


def _admin_coupon_to_read(c: ShopCoupon) -> CouponRead:
    return CouponRead(
        id=c.id,
        name=c.name,
        code=c.code,
        discount_amount=c.discount_amount,
        min_spend=c.min_spend,
        shop_name=c.shop_name,
        shop_url=c.shop_url,
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
        max_per_user=c.max_per_user,
        total_quota=c.total_quota,
        claimed_count=c.claimed_count,
        is_active=c.is_active,
        expires_at=c.expires_at,
        created_at=c.created_at,
    )


def _get_coupon_stats(db: Session) -> AdminCouponStats:
    total = db.scalar(select(func.count(ShopCoupon.id))) or 0
    assigned = db.scalar(select(func.count(ShopCoupon.id)).where(ShopCoupon.is_assigned.is_(True))) or 0
    unassigned = db.scalar(select(func.count(ShopCoupon.id)).where(ShopCoupon.is_assigned.is_(False))) or 0
    used = db.scalar(select(func.count(ShopCoupon.id)).where(ShopCoupon.is_used.is_(True))) or 0
    campaigns = db.scalar(select(func.count(CouponCampaign.id))) or 0

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
        val = max(0, payload.daily_drop_limit)
        set_setting_str(db, "coupon_daily_drop_limit", str(val))
    return _get_coupon_stats(db)


@router.get("/coupons", response_model=AdminCouponPageOut)
def admin_list_coupons(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: str = Query(default="all"),
    search: str = Query(default=""),
    db: Session = Depends(get_db),
) -> AdminCouponPageOut:
    stmt = select(ShopCoupon)
    if status == "assigned":
        stmt = stmt.where(ShopCoupon.is_assigned.is_(True))
    elif status == "unassigned":
        stmt = stmt.where(ShopCoupon.is_assigned.is_(False))
    elif status == "used":
        stmt = stmt.where(ShopCoupon.is_used.is_(True))

    if search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(ShopCoupon.code.ilike(term), ShopCoupon.name.ilike(term)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(ShopCoupon.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AdminCouponPageOut(
        items=[_admin_coupon_to_read(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


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
            shop_name=payload.shop_name.strip(),
            shop_url=payload.shop_url.strip(),
            is_assigned=False,
            expires_at=expires_at,
        )
        db.add(coupon)
        imported += 1

    db.commit()
    return AdminCouponImportResponse(
        success=True,
        imported_count=imported,
        skipped_count=skipped,
        message=f"成功导入 {imported} 张券码，跳过 {skipped} 张重复券码",
    )


@router.post("/coupons/sync-ldxp", response_model=AdminCouponImportResponse)
def admin_sync_ldxp_coupons(
    token: str = Query(default=""),
    db: Session = Depends(get_db),
) -> AdminCouponImportResponse:
    use_token = token.strip() or DEFAULT_LDXP_TOKEN
    try:
        batches = _fetch_ldxp_batches(use_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"调用 LDXP 接口失败: {e}")

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
                skipped += 1
                continue

            new_coupon = ShopCoupon(
                coupon_batch_id=coupon_id,
                name=name,
                code=code_str,
                discount_amount=discount,
                min_spend=min_spend,
                shop_name="彩头AI",
                shop_url="https://wzyp.cn/shop/pricememo",
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
    existing = db.scalar(select(CouponCampaign).where(CouponCampaign.campaign_code.ilike(code)))
    if existing:
        raise HTTPException(status_code=409, detail="该口令已存在")

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at or (now + timedelta(days=90))

    campaign = CouponCampaign(
        campaign_code=code,
        title=payload.title.strip(),
        coupon_batch_id=payload.coupon_batch_id,
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


