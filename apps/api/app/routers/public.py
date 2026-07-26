from __future__ import annotations

import hashlib
import ipaddress
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import Offer, Product, Report, ReportRateLimit, Shop
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
    ReportCreate,
    ReportOut,
    ShopDetail,
)
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

router = APIRouter(prefix="/api/v1", tags=["public"])
settings = get_settings()


def _offer_filters(
    *,
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
    product: str = Query(default="", max_length=160),
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
    sort: str = Query(default="price", pattern="^(price|price_desc|updated|offers)$"),
    db: Session = Depends(get_db),
) -> CatalogResponse:
    items = list_product_cards(
        db,
        q=q,
        platform=platform,
        product_slug=product,
        product_type=product_type,
        tag=tag,
        filters=_offer_filters(
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
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    comparable: bool | None = None,
    in_stock: bool = False,
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> CatalogOfferGroupPageResponse:
    current = get_snapshot(db, snapshot)
    items, total, offer_total, in_stock_count, last_updated_at = get_catalog_group_page(
        db,
        platform=platform,
        offset=offset,
        limit=limit,
        filters=_offer_filters(comparable=comparable, in_stock=in_stock),
        snapshot=current,
    )
    return CatalogOfferGroupPageResponse(
        items=items,
        total=total,
        offer_total=offer_total,
        in_stock_count=in_stock_count,
        last_updated_at=last_updated_at,
        snapshot_id=current.id if current else None,
        snapshot_at=current.published_at if current else None,
    )


@router.get("/products/{slug}", response_model=ProductDetail)
def product_detail(
    slug: str,
    delivery_type: str = Query(default="", max_length=40),
    period: str = Query(default="", max_length=40),
    warranty: str = Query(default="", max_length=40),
    auto_delivery: bool | None = None,
    updated_within_hours: int | None = Query(default=None, ge=1, le=24 * 7),
    comparable: bool | None = None,
    exclude: str = Query(default="", max_length=200),
    in_stock: bool = False,
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> ProductDetail:
    result = get_product_detail(
        db,
        slug,
        filters=_offer_filters(
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
        ),
        snapshot_id=snapshot,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="product not found")
    return result


@router.get("/products/{slug}/offers", response_model=OfferPageResponse)
def product_offers(
    slug: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> OfferPageResponse:
    items = get_product_offer_page(db, slug, offset=offset, limit=limit, snapshot_id=snapshot)
    if items is None:
        raise HTTPException(status_code=404, detail="product not found")
    return OfferPageResponse(items=items)


@router.get("/products/{slug}/groups", response_model=OfferGroupPageResponse)
def product_groups(
    slug: str,
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
            delivery_type=delivery_type,
            period=period,
            warranty=warranty,
            auto_delivery=auto_delivery,
            updated_within_hours=updated_within_hours,
            comparable=comparable,
            exclude=exclude,
            in_stock=in_stock,
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
    snapshot: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> GroupOffersResponse:
    items = get_group_offers(db, slug, fingerprint, snapshot_id=snapshot)
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
    return MetaResponse(
        platforms=sorted({x.platform for x in products}),
        product_types=sorted({x.product_type for x in products}),
        tags=sorted({tag for offer in offers for tag in (offer.tags or [])}),
    )


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate, request: Request, db: Session = Depends(get_db)) -> Report:
    _enforce_report_rate_limit(request, db)
    if payload.offer_id is not None and db.get(Offer, payload.offer_id) is None:
        raise HTTPException(status_code=404, detail="offer not found")
    report = Report(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
