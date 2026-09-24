from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import math
import re
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import false, func, select, text, update
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import (
    AdSlot,
    Offer,
    OfferClick,
    Product,
    RelayStation,
    Report,
    ReportRateLimit,
    Shop,
    SourceIntake,
    SystemSetting,
    User,
    UserActionLog,
)
from ..security import get_current_user, get_token_from_request, require_current_user
from ..schemas import (
    AdSlotListOut,
    CatalogOfferGroupPageResponse,
    PromoClickResponse,
    RelayStationListOut,
    CatalogResponse,
    CatalogSnapshotPublic,
    GroupOffersResponse,
    MetaResponse,
    SiteNoticeOut,
    CommunityNoticeOut,
    OfferClickResponse,
    OfferDescriptionResponse,
    OfferGroupPageResponse,
    OfferPageResponse,
    ProductDetail,
    ProductHistoryResponse,
    PublicCorrectionPage,
    ReportCreate,
    ReportOut,
    ShopDetail,
    ShopListResponse,
    ShopRequestCreate,
    ShopRequestOut,
    CommunitySkillDetailOut,
    CommunitySkillPageOut,
)
from ..services.community_skills import (
    get_community_skill_by_slug,
    list_community_skills,
    record_community_skill_copy,
)
from ..services.promo import (
    AD_SLOTS_ENABLED_KEY,
    RELAY_HUB_ENABLED_KEY,
    count_enabled_relay_stations,
    is_ad_live,
    list_enabled_relay_stations,
    list_live_ad_slots,
    setting_enabled,
)
from ..services.source_intake import enqueue_submission_notifications
from ..services.auth import get_session_by_token, settle_session_activity
from ..services.catalog import (
    OfferFilters,
    _base_public_offer_query,
    count_product_cards,
    get_catalog_group_page,
    get_current_snapshot,
    get_group_offers,
    get_offer_description,
    get_product_detail,
    get_product_history,
    get_product_group_page,
    get_product_offer_page,
    get_shop_detail,
    list_public_shop_tokens,
    list_public_shops,
    get_snapshot,
    list_product_cards,
    SnapshotNotFoundError,
)
from ..services.source_platform import (
    SOURCE_PLATFORM_LABELS,
    canonical_source_platform,
    get_disabled_source_platforms,
    prepare_source_submission,
    public_https_url_or_empty,
    source_platform_label,
    workflow_status,
)

router = APIRouter(prefix="/api/v1", tags=["public"])
settings = get_settings()


def _snapshot_or_404(db: Session, snapshot_id: int | None):
    try:
        return get_snapshot(db, snapshot_id)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _offer_filters(
    *,
    source_platform: str = "",
    delivery_type: str = "",
    period: str = "",
    warranty: str = "",
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = None,
    comparable: bool | None = None,
    exclude: str = "",
    in_stock: bool = False,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
) -> OfferFilters:
    return OfferFilters(
        source_platform=canonical_source_platform(source_platform),
        delivery_type=delivery_type,
        service_period=period,
        warranty=warranty,
        auto_delivery=auto_delivery,
        updated_within_hours=updated_within_hours,
        comparable=comparable,
        exclude=exclude,
        in_stock=in_stock,
        min_price=min_price,
        max_price=max_price,
    )


def _client_address(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer

    trusted_ranges = []
    for value in settings.trusted_proxy_cidrs.split(","):
        value = value.strip()
        if value:
            try:
                trusted_ranges.append(ipaddress.ip_network(value))
            except ValueError:
                continue
    if any(peer_ip in network for network in trusted_ranges):
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return str(peer_ip)


def _enforce_client_rate_limit(
    request: Request,
    db: Session,
    *,
    namespace: str,
    max_requests: int,
    window_seconds: int,
    detail: str,
) -> None:
    client_key = hashlib.sha256(
        f"{settings.admin_api_key}:{namespace}:{_client_address(request)}".encode()
    ).hexdigest()
    if db.get_bind().dialect.name == "postgresql":
        lock_key = int(client_key[:16], 16)
        if lock_key >= 2**63:
            lock_key -= 2**64
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})

    now = datetime.now(timezone.utc)
    window = timedelta(seconds=window_seconds)
    rate = db.get(ReportRateLimit, client_key)
    if rate is None:
        db.add(ReportRateLimit(client_key=client_key, window_started_at=now, request_count=1))
        # Commit immediately so the attempt is still counted when the endpoint
        # later fails validation and its transaction is rolled back/closed.
        db.commit()
        return

    started_at = rate.window_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    elapsed = now - started_at
    if elapsed >= window:
        rate.window_started_at = now
        rate.request_count = 1
        db.commit()
        return
    if rate.request_count >= max_requests:
        retry_after = max(1, math.ceil((window - elapsed).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )
    rate.request_count += 1
    db.commit()


def _enforce_report_rate_limit(request: Request, db: Session) -> None:
    _enforce_client_rate_limit(
        request,
        db,
        namespace="public-report",
        max_requests=settings.report_rate_limit_count,
        window_seconds=settings.report_rate_limit_window_seconds,
        detail="too many reports",
    )


@router.get("/products", response_model=CatalogResponse)
def products(
    q: str = Query(default="", max_length=100),
    platform: str = Query(default="", max_length=50),
    brand: str = Query(default="", max_length=50),
    product: str = Query(default="", max_length=160),
    products: str = Query(default="", max_length=4000),
    source_platform: str = Query(default="", max_length=50),
    product_type: str = Query(default="", max_length=60),
    tag: str = Query(default="", max_length=80),
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    snapshot: int | None = Query(default=None, ge=1),
    sort: str = Query(default="quality", pattern="^(quality|price|price_desc|updated|offers)$"),
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CatalogResponse:
    product_slugs = tuple(dict.fromkeys(value.strip().casefold() for value in products.split(",") if value.strip()))
    if len(product_slugs) > 20 or any(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,159}", value) is None for value in product_slugs):
        raise HTTPException(status_code=422, detail="products must contain at most 20 valid product slugs")
    current = _snapshot_or_404(db, snapshot)
    filters = _offer_filters(
        source_platform=source_platform,
        delivery_type=delivery_type,
        period=period,
        warranty=warranty,
        auto_delivery=auto_delivery,
        updated_within_hours=updated_within_hours,
        comparable=comparable,
        exclude=exclude,
        in_stock=in_stock,
        min_price=min_price,
        max_price=max_price,
    )
    catalog_args = {
        "q": q,
        "platform": brand or platform,
        "product_slug": product,
        "product_slugs": product_slugs,
        "product_type": product_type,
        "tag": tag,
        "filters": filters,
        "snapshot_id": current.id if current else None,
    }
    total = count_product_cards(db, **catalog_args)
    items = list_product_cards(db, **catalog_args, sort=sort, offset=offset, limit=limit)
    return CatalogResponse(
        items=items,
        total=total,
        offer_count=sum(item.offer_count for item in items),
        in_stock_count=sum(item.in_stock_count for item in items),
        comparable_offer_count=sum(item.comparable_offer_count for item in items),
        trusted_offer_count=sum(item.trusted_offer_count for item in items),
        metrics_note="报价统计范围为当前筛选条件、当前已发布快照和当前页商品。",
        snapshot_id=current.id if current else None,
        snapshot_at=current.published_at if current else None,
    )


@router.get("/snapshot", response_model=CatalogSnapshotPublic)
def snapshot(db: Session = Depends(get_db)) -> CatalogSnapshotPublic:
    current = get_current_snapshot(db)
    return CatalogSnapshotPublic(
        id=current.id if current else None,
        published_at=current.published_at if current else None,
    )


@router.get("/catalog/groups", response_model=CatalogOfferGroupPageResponse)
def catalog_groups(
    q: str = Query(default="", max_length=100),
    platform: str = Query(default="", max_length=50),
    brand: str = Query(default="", max_length=50),
    product: str = Query(default="", max_length=160),
    source_platform: str = Query(default="", max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> CatalogOfferGroupPageResponse:
    current = _snapshot_or_404(db, snapshot)
    items, total, offer_total, in_stock_count, comparable_offer_count, trusted_offer_count, last_updated_at = get_catalog_group_page(
        db,
        q=q,
        platform=brand or platform,
        product_slug=product,
        offset=offset,
        limit=limit,
        filters=_offer_filters(
            source_platform=source_platform,
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
            min_price=min_price,
            max_price=max_price,
        ),
        snapshot=current,
    )
    return CatalogOfferGroupPageResponse(
        items=items,
        total=total,
        offer_total=offer_total,
        in_stock_count=in_stock_count,
        comparable_offer_count=comparable_offer_count,
        trusted_offer_count=trusted_offer_count,
        last_updated_at=last_updated_at,
        snapshot_id=current.id if current else None,
        snapshot_at=current.published_at if current else None,
    )


@router.get("/products/{slug}", response_model=ProductDetail)
def product_detail(
    slug: str,
    source_platform: str = Query(default="", max_length=50),
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> ProductDetail:
    current = _snapshot_or_404(db, snapshot)
    result = get_product_detail(
        db,
        slug,
        filters=_offer_filters(
            source_platform=source_platform,
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
            min_price=min_price,
            max_price=max_price,
        ),
        snapshot_id=current.id if current else None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="product not found")
    return result


@router.get("/products/{slug}/history", response_model=ProductHistoryResponse)
def product_history(
    slug: str,
    source_platform: str = Query(default="", max_length=50),
    db: Session = Depends(get_db),
) -> ProductHistoryResponse:
    result = get_product_history(
        db,
        slug,
        source_platform=_offer_filters(source_platform=source_platform).source_platform,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="product not found")
    return result


@router.get("/products/{slug}/offers", response_model=OfferPageResponse)
def product_offers(
    slug: str,
    source_platform: str = Query(default="", max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> OfferPageResponse:
    current = _snapshot_or_404(db, snapshot)
    items = get_product_offer_page(
        db,
        slug,
        offset=offset,
        limit=limit,
        filters=_offer_filters(source_platform=source_platform),
        snapshot_id=current.id if current else None,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="product not found")
    return OfferPageResponse(items=items)


@router.get("/products/{slug}/groups", response_model=OfferGroupPageResponse)
def product_groups(
    slug: str,
    source_platform: str = Query(default="", max_length=50),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> OfferGroupPageResponse:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    current = _snapshot_or_404(db, snapshot)
    items, total, offer_total = get_product_group_page(
        db,
        product.id,
        offset=offset,
        limit=limit,
        filters=_offer_filters(
            source_platform=source_platform,
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
            min_price=min_price,
            max_price=max_price,
        ),
        snapshot=current,
    )
    return OfferGroupPageResponse(
        items=items,
        total=total,
        offer_total=offer_total,
        snapshot_id=current.id if current else None,
    )


@router.get("/products/{slug}/groups/{fingerprint}", response_model=GroupOffersResponse)
def product_group_offers(
    slug: str,
    fingerprint: str,
    currency: str = Query(default="", min_length=0, max_length=10),
    source_platform: str = Query(default="", max_length=50),
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> GroupOffersResponse:
    current = _snapshot_or_404(db, snapshot)
    items = get_group_offers(
        db,
        slug,
        fingerprint,
        currency=currency,
        filters=_offer_filters(
            source_platform=source_platform,
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
            min_price=min_price,
            max_price=max_price,
        ),
        snapshot_id=current.id if current else None,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="product not found")
    return GroupOffersResponse(items=items)


@router.get("/offers/{offer_id}/description", response_model=OfferDescriptionResponse)
def offer_description(offer_id: int, db: Session = Depends(get_db)) -> OfferDescriptionResponse:
    description = get_offer_description(db, offer_id)
    if description is None:
        raise HTTPException(status_code=404, detail="offer not found")
    return OfferDescriptionResponse(offer_id=offer_id, original_description=description)


@router.get("/shops", response_model=list[str])
def shops(db: Session = Depends(get_db)) -> list[str]:
    return list_public_shop_tokens(db)


@router.get("/shops/cards", response_model=ShopListResponse)
def shop_cards(
    source_platform: str = Query("", description="Filter by source platform, e.g. 16688"),
    q: str = Query("", description="Search shop name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("offer_count", description="Sort: offer_count | name | last_seen"),
    db: Session = Depends(get_db),
) -> ShopListResponse:
    return list_public_shops(
        db,
        source_platform=source_platform,
        q=q,
        offset=offset,
        limit=limit,
        sort=sort,
    )


@router.get("/shops/tokens", response_model=list[str])
def shop_tokens(db: Session = Depends(get_db)) -> list[str]:
    """Return a flat list of shop tokens (used by sitemap and legacy callers)."""
    return list_public_shop_tokens(db)


@router.get("/shops/{token}", response_model=ShopDetail)
def shop_detail(
    token: str,
    offer_offset: int = Query(default=0, ge=0, le=10000),
    offer_limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ShopDetail:
    result = get_shop_detail(db, token, offer_offset=offer_offset, offer_limit=offer_limit)
    if result is None:
        raise HTTPException(status_code=404, detail="shop not found")
    return result


@router.get("/meta", response_model=MetaResponse)
def meta(db: Session = Depends(get_db)) -> MetaResponse:
    brands = sorted(
        value
        for value in db.scalars(
            select(Product.platform)
            .where(Product.is_visible.is_(True), Product.platform != "")
            .distinct()
        )
        if value
    )
    product_types = sorted(
        value
        for value in db.scalars(
            select(Product.product_type)
            .where(Product.is_visible.is_(True), Product.product_type != "")
            .distinct()
        )
        if value
    )
    current = get_current_snapshot(db)
    disabled_platforms = get_disabled_source_platforms()
    offer_conditions = [
        Offer.active.is_(True),
        Offer.approved.is_(True),
        (Offer.hidden_reason.is_(None) | (func.trim(Offer.hidden_reason) == "")),
        Shop.is_visible.is_(True),
        Product.is_visible.is_(True),
        Offer.observed_at >= datetime.now(timezone.utc) - timedelta(hours=settings.stale_offer_hours),
    ]
    if disabled_platforms:
        offer_conditions.append(Shop.platform.notin_(disabled_platforms))
    source_platform_ids = sorted({
        canonical_source_platform(value)
        for value in db.scalars(
            select(Shop.platform)
            .join(Offer, Offer.shop_id == Shop.id)
            .join(Product, Offer.product_id == Product.id)
            .where(*offer_conditions)
            .where(Offer.snapshot_id == current.id if current is not None else false())
            .distinct()
        )
        if value
    })
    tag_rows = db.scalars(
        select(Offer.tags)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(Product, Offer.product_id == Product.id)
        .where(*offer_conditions)
        .where(Offer.snapshot_id == current.id if current is not None else false())
    )
    tags = sorted({tag for row in tag_rows for tag in (row or [])})
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "advertise_enabled"))
    advertise_enabled = bool(setting and setting.value and setting.value.strip().lower() in ("true", "1", "yes", "on"))

    notice_setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "site_notice_enabled"))
    notice_enabled = True if not notice_setting or not notice_setting.value else notice_setting.value.strip().lower() in ("true", "1", "yes", "on")

    def _get_setting_val(key: str, default: str = "") -> str:
        s = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        return s.value if s and s.value is not None else default

    def _public_link_or_empty(value: str, *, allow_internal: bool = False) -> str:
        cleaned = value.strip()
        if allow_internal and cleaned.startswith("/") and not cleaned.startswith("//") and "\\" not in cleaned:
            return cleaned
        return public_https_url_or_empty(cleaned)

    site_notice = SiteNoticeOut(
        enabled=notice_enabled,
        badge=_get_setting_val("site_notice_badge", "最新动态"),
        title=_get_setting_val("site_notice_title", "已支持 16688 平台商户比价与 Agent 开放快照"),
        content=_get_setting_val("site_notice_content", "我们新增了 16688 渠道 AI 商品实时抓取，并上线了面向 AI Agent 与开发者的全站静态只读 Feed。"),
        link_text=_get_setting_val("site_notice_link_text", "查看开发文档"),
        link_url=_public_link_or_empty(
            _get_setting_val("site_notice_link_url", "/developers"),
            allow_internal=True,
        ),
    )

    comm_setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "community_enabled"))
    comm_enabled = True if not comm_setting or not comm_setting.value else comm_setting.value.strip().lower() in ("true", "1", "yes", "on")

    community_notice = CommunityNoticeOut(
        enabled=comm_enabled,
        title=_get_setting_val("community_title", "加入 AI 比价交流群"),
        desc=_get_setting_val("community_desc", "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。"),
        qq_group=_get_setting_val("community_qq_group", "938741334"),
        qq_url=_public_link_or_empty(_get_setting_val("community_qq_url", "")),
        btn_text=_get_setting_val("community_btn_text", "一键加入 QQ 群"),
    )

    bot_setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled"))
    bot_enabled = True if not bot_setting or not bot_setting.value else bot_setting.value.strip().lower() in ("true", "1", "yes", "on")
    ad_slots_enabled = setting_enabled(db, AD_SLOTS_ENABLED_KEY, default=True)
    relay_hub_enabled = setting_enabled(db, RELAY_HUB_ENABLED_KEY, default=True)

    return MetaResponse(
        platforms=brands,
        brands=brands,
        source_platforms=[
            {"id": platform_id, "label": source_platform_label(platform_id)}
            for platform_id in source_platform_ids
            if platform_id in SOURCE_PLATFORM_LABELS and platform_id not in disabled_platforms
        ],
        product_types=product_types,
        tags=tags,
        advertise_enabled=advertise_enabled,
        ad_slots_enabled=ad_slots_enabled,
        relay_hub_enabled=relay_hub_enabled,
        relay_station_count=count_enabled_relay_stations(db) if relay_hub_enabled else 0,
        bot_enabled=bot_enabled,
        site_notice=site_notice,
        community_notice=community_notice,
    )


@router.get("/corrections", response_model=PublicCorrectionPage)
def public_corrections(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PublicCorrectionPage:
    base = select(Report).where(
        Report.status == "resolved",
        Report.kind != "shop_request",
        Report.public_summary != "",
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(db.scalars(base.order_by(Report.resolved_at.desc(), Report.id.desc()).offset(offset).limit(limit)))
    return PublicCorrectionPage(
        items=[{
            "id": row.id,
            "offer_id": row.offer_id,
            "kind": row.kind,
            "public_summary": row.public_summary,
            "merchant_response": row.merchant_response,
            "resolved_at": row.resolved_at,
            "created_at": row.created_at,
        } for row in rows],
        total=total,
    )


def _watch_targets(value: str) -> list[tuple[str, Decimal | None]]:
    targets: list[tuple[str, Decimal | None]] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        slug, _, raw_price = raw.partition(":")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,159}", slug):
            continue
        threshold = None
        if raw_price:
            try:
                threshold = Decimal(raw_price).quantize(Decimal("0.01"))
            except Exception:
                continue
            if not threshold.is_finite() or threshold <= 0:
                continue
        targets.append((slug, threshold))
        if len(targets) >= 20:
            break
    return targets


@router.get("/watch.atom", response_class=Response)
def watch_feed(
    targets: str = Query(
        default="",
        max_length=1000,
        description="逗号分隔的关注目标，格式为 product-slug[:目标价]，例如 chatgpt-plus:16",
    ),
    db: Session = Depends(get_db),
) -> Response:
    parsed = _watch_targets(targets)
    if not parsed:
        raise HTTPException(status_code=422, detail="至少提供一个有效关注目标，请使用 targets=product-slug[:目标价]")
    now = datetime.now(timezone.utc)
    entries: list[str] = []
    latest: datetime | None = None
    for slug, threshold in parsed:
        cards = list_product_cards(db, product_slug=slug, sort="quality")
        if not cards:
            continue
        card = cards[0]
        updated = card.last_updated_at or now
        updated = updated if updated.tzinfo is not None else updated.replace(tzinfo=timezone.utc)
        latest = updated if latest is None else max(latest, updated)
        price = card.lowest_price
        hit = card.in_stock_count > 0 and (threshold is None or (price is not None and price <= threshold))
        state = "达到提醒条件" if hit else "持续关注"
        price_text = f"{card.price_currency} {price:.2f}" if price is not None else "暂无可信价格"
        threshold_text = f"，目标价 {card.price_currency} {threshold:.2f}" if threshold is not None else ""
        content = f"{card.display_name}：{price_text}，{card.in_stock_count} 条有货，{card.trusted_offer_count} 条可信报价{threshold_text}。状态：{state}。"
        entry_id = hashlib.sha256(f"{slug}:{card.price_currency}:{price}:{card.in_stock_count}:{threshold}:{card.last_updated_at}".encode()).hexdigest()
        url = f"{str(settings.public_site_url).rstrip('/')}/products/{urllib.parse.quote(slug)}"
        entries.append(
            "<entry>"
            f"<id>urn:ai-price-radar:{entry_id}</id>"
            f"<title>{html.escape(card.display_name)} · {html.escape(state)}</title>"
            f"<link href=\"{html.escape(url)}\"/>"
            f"<updated>{updated.isoformat()}</updated>"
            f"<content type=\"text\">{html.escape(content)}</content>"
            "</entry>"
        )
    if not entries:
        raise HTTPException(status_code=404, detail="关注产品不存在")
    feed_id = hashlib.sha256(targets.encode()).hexdigest()
    watch_url = str(settings.public_site_url).rstrip("/") + "/watchlist"
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f'<id>urn:ai-price-radar:watch:{feed_id}</id>'
        '<title>AI Price Memory 价格与补货关注</title>'
        f'<updated>{(latest or now).isoformat()}</updated>'
        f'<link href="{html.escape(watch_url)}"/>'
        + "".join(entries)
        + '</feed>'
    )
    return Response(content=body, media_type="application/atom+xml; charset=utf-8", headers={"Cache-Control": "public, max-age=300"})


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate, request: Request, db: Session = Depends(get_db)) -> Report:
    _enforce_report_rate_limit(request, db)
    if payload.kind == "shop_request":
        raise HTTPException(status_code=422, detail="use /api/v1/shop-requests for shop applications")
    product_slug = payload.product_slug
    if product_slug is not None:
        product_slug = db.scalar(
            select(Product.slug).where(Product.slug == product_slug, Product.is_visible.is_(True))
        )
        if product_slug is None:
            raise HTTPException(status_code=404, detail="product not found")

    if payload.offer_id is not None:
        public_offer = db.scalar(
            _base_public_offer_query(db, include_details=False)
            .join(Product, Offer.product_id == Product.id)
            .where(Offer.id == payload.offer_id, Product.is_visible.is_(True))
        )
        if public_offer is None:
            raise HTTPException(status_code=404, detail="offer not found")
        offer_product_slug = db.scalar(select(Product.slug).where(Product.id == public_offer.product_id))
        if product_slug is not None and product_slug != offer_product_slug:
            raise HTTPException(status_code=422, detail="offer does not belong to product")
        product_slug = offer_product_slug

    report = Report(**payload.model_dump(exclude={"product_slug"}), product_slug=product_slug)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/shop-requests", response_model=ShopRequestOut)
def create_shop_request(
    payload: ShopRequestCreate,
    request: Request,
    response: Response,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> ShopRequestOut:
    _enforce_report_rate_limit(request, db)
    if not current_user.email or current_user.email.casefold() != payload.contact.casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="contact email must match the verified account email",
        )
    declared_platform = canonical_source_platform(payload.declared_platform or payload.source_type)
    try:
        submission = prepare_source_submission(payload.shop_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    detected_platform = "unknown"
    persisted_source_type = "unknown"
    source_key = submission.source_key
    shop_url = submission.source_url
    token = submission.shop_token
    detection_message = "来源已提交，正在等待隔离检测器确认来源类型和公开契约。"
    db.add(
        UserActionLog(
            user_id=current_user.id,
            action_type="shop_request_authorization",
            action_name="确认有权提交公开来源",
            target_id=source_key[:100],
            page="/shops/submit",
            extra_data={
                "consent_version": payload.consent_version,
                "declared_platform": declared_platform,
            },
            created_at=datetime.now(timezone.utc),
        )
    )

    def build_response(
        status_value: str,
        response_status: str,
        *,
        request_id: int | None = None,
    ) -> ShopRequestOut:
        return ShopRequestOut(
            source_type=payload.source_type,
            declared_platform=declared_platform,
            detected_platform=detected_platform,
            detection_message=detection_message,
            workflow_status=workflow_status(status_value),
            status=response_status,
            request_id=request_id,
            shop_token=token,
        )

    known_shop = db.scalar(select(Shop.id).where(
        Shop.is_visible.is_(True),
        (func.lower(Shop.token) == token.lower()) | (func.lower(Shop.source_url) == shop_url.lower())
    ))
    if known_shop is not None:
        db.commit()
        return build_response("published", "already_known")

    existing = db.scalar(
        select(SourceIntake)
        .where(SourceIntake.source_key == source_key)
        .order_by(SourceIntake.id.desc())
    )
    if existing is not None:
        db.commit()
        response_status = "already_known" if workflow_status(existing.status) == "published" else "already_pending"
        return build_response(existing.status, response_status, request_id=existing.id)

    intake_values = {
        "source_type": persisted_source_type,
        "declared_platform": declared_platform,
        "detected_platform": detected_platform,
        "source_key": source_key,
        "source_url": shop_url,
        "shop_name": payload.shop_name.strip(),
        "contact_email": payload.contact.strip(),
        "note": payload.note.strip(),
        "origin": "manual",
        "status": "submitted",
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        insert_result = db.execute(
            insert(SourceIntake)
            .values(**intake_values)
            .on_conflict_do_nothing(index_elements=["source_type", "source_key"])
        )
        intake = db.scalar(
            select(SourceIntake).where(
                SourceIntake.source_type == persisted_source_type,
                SourceIntake.source_key == source_key,
            )
        )
        if insert_result.rowcount == 0:
            db.commit()
            existing_status = intake.status if intake else "submitted"
            response_status = "already_known" if workflow_status(existing_status) == "published" else "already_pending"
            return build_response(existing_status, response_status, request_id=intake.id if intake else None)
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        insert_result = db.execute(
            insert(SourceIntake)
            .values(**intake_values)
            .on_conflict_do_nothing(index_elements=["source_type", "source_key"])
        )
        intake = db.scalar(
            select(SourceIntake).where(
                SourceIntake.source_type == persisted_source_type,
                SourceIntake.source_key == source_key,
            )
        )
        if insert_result.rowcount == 0:
            db.commit()
            existing_status = intake.status if intake else "submitted"
            response_status = "already_known" if workflow_status(existing_status) == "published" else "already_pending"
            return build_response(existing_status, response_status, request_id=intake.id if intake else None)
    else:
        intake = SourceIntake(**intake_values)
        db.add(intake)
        db.flush()
    if intake is None:
        raise HTTPException(status_code=500, detail="failed to create source intake")
    enqueue_submission_notifications(db, intake)
    db.commit()
    db.refresh(intake)
    response.status_code = status.HTTP_201_CREATED
    return build_response("submitted", "submitted", request_id=intake.id)


@router.get("/skills", response_model=CommunitySkillPageOut)
def public_community_skills(
    kind: str = Query(default="", max_length=40),
    tag: str = Query(default="", max_length=50),
    model: str = Query(default="", max_length=50),
    q: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CommunitySkillPageOut:
    k = kind if isinstance(kind, str) else ""
    t = tag if isinstance(tag, str) else ""
    m = model if isinstance(model, str) else ""
    query_str = q if isinstance(q, str) else ""
    p = page if isinstance(page, int) else 1
    ps = page_size if isinstance(page_size, int) else 20
    return list_community_skills(
        db,
        kind=k or None,
        tag=t or None,
        model=m or None,
        search=query_str or None,
        page=p,
        page_size=ps,
        visible_only=True,
    )



@router.get("/skills/{slug}", response_model=CommunitySkillDetailOut)
def public_community_skill_detail(
    slug: str,
    db: Session = Depends(get_db),
) -> CommunitySkillDetailOut:
    skill = get_community_skill_by_slug(db, slug, visible_only=True, increment_view=True)
    if not skill:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


@router.post("/skills/{slug}/copy")
def public_community_skill_copy(
    slug: str,
    db: Session = Depends(get_db),
):
    if not record_community_skill_copy(db, slug):
        raise HTTPException(status_code=404, detail="skill not found")
    return {"status": "ok"}


# Serializes the debounce-check + insert for click tracking within this process
# so concurrent requests cannot both pass the 60s debounce (single-instance deployment).
_CLICK_DEBOUNCE_LOCK = threading.Lock()


def _click_ip_hash(namespace: str, client_ip: str) -> str:
    return hmac.new(
        settings.session_secret_key.encode("utf-8"),
        f"{namespace}:{client_ip}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def _settle_click_user_activity(db: Session, request: Request, current_user: User | None, now: datetime) -> None:
    """Settle online-duration accounting and atomically bump the user click counter."""
    if not current_user:
        return
    token = get_token_from_request(request)
    session = get_session_by_token(db, token) if token else None
    settle_session_activity(db, current_user, session, now=now)
    db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(button_click_count=User.button_click_count + 1)
    )


@router.post("/offers/{offer_id}/click", response_model=OfferClickResponse)
def record_offer_click(
    offer_id: int,
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfferClickResponse:
    offer = db.scalar(
        _base_public_offer_query(db)
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.id == offer_id, Product.is_visible.is_(True))
    )
    if not offer:
        raise HTTPException(status_code=404, detail="offer not found")

    client_ip = _client_address(request)
    ip_hash = _click_ip_hash("offer-click", client_ip)
    user_agent = (request.headers.get("user-agent") or "")[:500]
    now = datetime.now(timezone.utc)

    # 60-second debounce per IP per offer
    debounce_cutoff = now - timedelta(seconds=60)
    with _CLICK_DEBOUNCE_LOCK:
        existing_click = db.scalar(
            select(OfferClick.id).where(
                OfferClick.offer_id == offer.id,
                OfferClick.ip_hash == ip_hash,
                OfferClick.created_at >= debounce_cutoff,
            ).limit(1)
        )

        if existing_click:
            return OfferClickResponse(
                success=True,
                recorded=False,
                click_count=int(offer.click_count or 0),
            )

        product_slug = offer.product.slug if offer.product else None
        user_id = current_user.id if current_user else None
        click = OfferClick(
            offer_id=offer.id,
            shop_id=offer.shop_id,
            user_id=user_id,
            product_slug=product_slug,
            ip_hash=ip_hash,
            user_agent=user_agent,
        )
        db.add(click)
        # Atomic increment: read-modify-write loses updates under concurrency.
        db.execute(
            update(Offer).where(Offer.id == offer.id).values(click_count=Offer.click_count + 1)
        )

        _settle_click_user_activity(db, request, current_user, now)

        db.add(
            UserActionLog(
                user_id=user_id,
                action_type="offer_click",
                action_name="去购买 (商品直达)",
                target_id=str(offer.id),
                page=f"/products/{product_slug}" if product_slug else "/",
                ip_address=client_ip,
                user_agent=user_agent,
                extra_data={"shop_id": offer.shop_id, "price": str(offer.price) if offer.price else None},
                created_at=now,
            )
        )

        db.commit()
        db.refresh(offer)

    return OfferClickResponse(
        success=True,
        recorded=True,
        click_count=int(offer.click_count or 0),
    )


@router.post("/shops/{token}/click", response_model=OfferClickResponse)
def record_shop_click(
    token: str,
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfferClickResponse:
    shop = db.scalar(select(Shop).where(Shop.token == token, Shop.is_visible.is_(True)))
    if not shop:
        raise HTTPException(status_code=404, detail="shop not found")
    public_offer_id = db.scalar(
        _base_public_offer_query(db, include_details=False)
        .where(Offer.shop_id == shop.id)
        .limit(1)
    )
    if public_offer_id is None:
        raise HTTPException(status_code=404, detail="shop not found")

    client_ip = _client_address(request)
    ip_hash = _click_ip_hash("shop-click", client_ip)
    user_agent = (request.headers.get("user-agent") or "")[:500]
    now = datetime.now(timezone.utc)

    # 60-second debounce per IP per shop
    debounce_cutoff = now - timedelta(seconds=60)
    with _CLICK_DEBOUNCE_LOCK:
        existing_click = db.scalar(
            select(OfferClick.id).where(
                OfferClick.shop_id == shop.id,
                OfferClick.offer_id.is_(None),
                OfferClick.ip_hash == ip_hash,
                OfferClick.created_at >= debounce_cutoff,
            ).limit(1)
        )

        if existing_click:
            return OfferClickResponse(success=True, recorded=False, click_count=0)

        user_id = current_user.id if current_user else None
        click = OfferClick(
            offer_id=None,
            shop_id=shop.id,
            user_id=user_id,
            product_slug=None,
            ip_hash=ip_hash,
            user_agent=user_agent,
        )
        db.add(click)

        _settle_click_user_activity(db, request, current_user, now)

        db.add(
            UserActionLog(
                user_id=user_id,
                action_type="shop_click",
                action_name="访问店铺 (商户直达)",
                target_id=shop.token,
                page=f"/shops/{shop.token}",
                ip_address=client_ip,
                user_agent=user_agent,
                extra_data={"shop_name": shop.name},
                created_at=now,
            )
        )

        db.commit()

    return OfferClickResponse(success=True, recorded=True, click_count=0)


# ---------------------------------------------------------------------------
# Ad slots (广告栏位) and relay stations (中转站)
# ---------------------------------------------------------------------------


@router.get("/ads", response_model=AdSlotListOut)
def public_ad_slots(
    placement: str = Query(default="", max_length=40),
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> AdSlotListOut:
    if not setting_enabled(db, AD_SLOTS_ENABLED_KEY, default=True):
        return AdSlotListOut(items=[], enabled=False)
    return AdSlotListOut(items=list_live_ad_slots(db, placement=placement.strip(), limit=limit), enabled=True)


@router.post("/ads/{slot_id}/click", response_model=PromoClickResponse)
def record_ad_click(slot_id: int, request: Request, db: Session = Depends(get_db)) -> PromoClickResponse:
    slot = db.get(AdSlot, slot_id)
    if slot is None or not is_ad_live(slot) or not setting_enabled(db, AD_SLOTS_ENABLED_KEY, default=True):
        raise HTTPException(status_code=404, detail="ad slot not found")
    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"ad-click:{slot_id}",
        max_requests=5,
        window_seconds=60,
        detail="点击过于频繁，请稍后再试",
    )
    db.execute(update(AdSlot).where(AdSlot.id == slot_id).values(click_count=AdSlot.click_count + 1))
    db.commit()
    refreshed = db.get(AdSlot, slot_id)
    return PromoClickResponse(status="ok", click_count=int(refreshed.click_count or 0) if refreshed else 0)


@router.get("/relays", response_model=RelayStationListOut)
def public_relay_stations(db: Session = Depends(get_db)) -> RelayStationListOut:
    if not setting_enabled(db, RELAY_HUB_ENABLED_KEY, default=True):
        return RelayStationListOut(items=[], total=0, enabled=False)
    items = list_enabled_relay_stations(db)
    return RelayStationListOut(items=items, total=len(items), enabled=True)


@router.post("/relays/{station_id}/click", response_model=PromoClickResponse)
def record_relay_click(station_id: int, request: Request, db: Session = Depends(get_db)) -> PromoClickResponse:
    station = db.get(RelayStation, station_id)
    if station is None or not station.is_enabled or not setting_enabled(db, RELAY_HUB_ENABLED_KEY, default=True):
        raise HTTPException(status_code=404, detail="relay station not found")
    _enforce_client_rate_limit(
        request,
        db,
        namespace=f"relay-click:{station_id}",
        max_requests=5,
        window_seconds=60,
        detail="点击过于频繁，请稍后再试",
    )
    db.execute(update(RelayStation).where(RelayStation.id == station_id).values(click_count=RelayStation.click_count + 1))
    db.commit()
    refreshed = db.get(RelayStation, station_id)
    return PromoClickResponse(status="ok", click_count=int(refreshed.click_count or 0) if refreshed else 0)
