from __future__ import annotations

import hashlib
import html
import ipaddress
import math
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import Offer, Product, Report, ReportRateLimit, Shop, SourceIntake
from ..schemas import (
    CatalogOfferGroupPageResponse,
    CatalogResponse,
    CatalogSnapshotPublic,
    GroupOffersResponse,
    MetaResponse,
    OfferDescriptionResponse,
    OfferGroupPageResponse,
    OfferPageResponse,
    ProductDetail,
    PublicCorrectionPage,
    ReportCreate,
    ReportOut,
    ShopDetail,
    ShopRequestCreate,
    ShopRequestOut,
)
from ..services.source_intake import enqueue_submission_notifications
from ..services.catalog import (
    OfferFilters,
    get_catalog_group_page,
    get_current_snapshot,
    get_group_offers,
    get_offer_description,
    get_product_detail,
    get_product_group_page,
    get_product_offer_page,
    get_shop_detail,
    get_snapshot,
    list_product_cards,
)
from ..services.source_platform import (
    SOURCE_PLATFORM_LABELS,
    canonical_source_platform,
    prepare_source_submission,
    source_platform_label,
    workflow_status,
)

router = APIRouter(prefix="/api/v1", tags=["public"])
settings = get_settings()
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


def _enforce_report_rate_limit(request: Request, db: Session) -> None:
    client_key = hashlib.sha256(
        f"{settings.admin_api_key}:{_client_address(request)}".encode()
    ).hexdigest()
    if db.get_bind().dialect.name == "postgresql":
        lock_key = int(client_key[:16], 16)
        if lock_key >= 2**63:
            lock_key -= 2**64
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})

    now = datetime.now(timezone.utc)
    window = timedelta(seconds=settings.report_rate_limit_window_seconds)
    rate = db.get(ReportRateLimit, client_key)
    if rate is None:
        db.add(ReportRateLimit(client_key=client_key, window_started_at=now, request_count=1))
        return

    started_at = rate.window_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    elapsed = now - started_at
    if elapsed >= window:
        rate.window_started_at = now
        rate.request_count = 1
        return
    if rate.request_count >= settings.report_rate_limit_count:
        retry_after = max(1, math.ceil((window - elapsed).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many reports",
            headers={"Retry-After": str(retry_after)},
        )
    rate.request_count += 1


@router.get("/products", response_model=CatalogResponse)
def products(
    q: str = Query(default="", max_length=100),
    platform: str = Query(default="", max_length=50),
    brand: str = Query(default="", max_length=50),
    product: str = Query(default="", max_length=160),
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
    db: Session = Depends(get_db),
) -> CatalogResponse:
    items = list_product_cards(
        db,
        q=q,
        platform=brand or platform,
        product_slug=product,
        product_type=product_type,
        tag=tag,
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
        sort=sort,
        snapshot_id=snapshot,
    )
    current = get_snapshot(db, snapshot)
    return CatalogResponse(
        items=items,
        total=len(items),
        offer_count=sum(item.offer_count for item in items),
        in_stock_count=sum(item.in_stock_count for item in items),
        comparable_offer_count=sum(item.comparable_offer_count for item in items),
        trusted_offer_count=sum(item.trusted_offer_count for item in items),
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
    current = get_snapshot(db, snapshot)
    items, total, offer_total, in_stock_count, comparable_offer_count, trusted_offer_count, last_updated_at = get_catalog_group_page(
        db,
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
        snapshot_id=snapshot,
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
    items = get_product_offer_page(
        db,
        slug,
        offset=offset,
        limit=limit,
        filters=_offer_filters(source_platform=source_platform),
        snapshot_id=snapshot,
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
    current = get_snapshot(db, snapshot)
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
    in_stock: bool = False,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> GroupOffersResponse:
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
            in_stock=in_stock,
            min_price=min_price,
            max_price=max_price,
        ),
        snapshot_id=snapshot,
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


@router.get("/shops/{token}", response_model=ShopDetail)
def shop_detail(token: str, db: Session = Depends(get_db)) -> ShopDetail:
    result = get_shop_detail(db, token)
    if result is None:
        raise HTTPException(status_code=404, detail="shop not found")
    return result


@router.get("/meta", response_model=MetaResponse)
def meta(db: Session = Depends(get_db)) -> MetaResponse:
    products = list(db.scalars(select(Product).where(Product.is_visible.is_(True))))
    current = get_current_snapshot(db)
    offer_stmt = (
        select(Offer)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Shop.is_visible.is_(True),
            Offer.observed_at >= datetime.now(timezone.utc) - timedelta(hours=settings.stale_offer_hours),
        )
    )
    if current is not None:
        offer_stmt = offer_stmt.where(Offer.snapshot_id == current.id)
    offers = list(db.scalars(offer_stmt))
    brands = sorted({x.platform for x in products})
    source_platform_ids = sorted({canonical_source_platform(offer.shop.platform) for offer in offers})
    return MetaResponse(
        platforms=brands,
        brands=brands,
        source_platforms=[
            {"id": platform_id, "label": source_platform_label(platform_id)}
            for platform_id in source_platform_ids
            if platform_id in SOURCE_PLATFORM_LABELS
        ],
        product_types=sorted({x.product_type for x in products}),
        tags=sorted({tag for offer in offers for tag in (offer.tags or [])}),
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
            if threshold <= 0:
                continue
        targets.append((slug, threshold))
        if len(targets) >= 20:
            break
    return targets


@router.get("/watch.atom", response_class=Response)
def watch_feed(
    targets: str = Query(default="", max_length=1000),
    db: Session = Depends(get_db),
) -> Response:
    parsed = _watch_targets(targets)
    if not parsed:
        raise HTTPException(status_code=422, detail="至少提供一个有效关注目标")
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
        '<title>AI Price Radar 价格与补货关注</title>'
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
    if payload.offer_id is not None and db.get(Offer, payload.offer_id) is None:
        raise HTTPException(status_code=404, detail="offer not found")
    report = Report(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/shop-requests", response_model=ShopRequestOut)
def create_shop_request(
    payload: ShopRequestCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ShopRequestOut:
    _enforce_report_rate_limit(request, db)
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
