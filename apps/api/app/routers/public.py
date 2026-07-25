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
from ..models import Offer, Product, Report, ReportRateLimit
from ..schemas import CatalogResponse, MetaResponse, OfferPageResponse, ProductDetail, ReportCreate, ReportOut, ShopDetail
from ..services.catalog import get_product_detail, get_product_offer_page, get_shop_detail, list_product_cards

router = APIRouter(prefix="/api/v1", tags=["public"])
settings = get_settings()


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
        in_stock=in_stock,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return CatalogResponse(items=items, total=len(items))


@router.get("/products/{slug}", response_model=ProductDetail)
def product_detail(slug: str, db: Session = Depends(get_db)) -> ProductDetail:
    result = get_product_detail(db, slug)
    if result is None:
        raise HTTPException(status_code=404, detail="product not found")
    return result


@router.get("/products/{slug}/offers", response_model=OfferPageResponse)
def product_offers(
    slug: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> OfferPageResponse:
    items = get_product_offer_page(db, slug, offset=offset, limit=limit)
    if items is None:
        raise HTTPException(status_code=404, detail="product not found")
    return OfferPageResponse(items=items)


@router.get("/shops/{token}", response_model=ShopDetail)
def shop_detail(token: str, db: Session = Depends(get_db)) -> ShopDetail:
    result = get_shop_detail(db, token)
    if result is None:
        raise HTTPException(status_code=404, detail="shop not found")
    return result


@router.get("/meta", response_model=MetaResponse)
def meta(db: Session = Depends(get_db)) -> MetaResponse:
    products = list(db.scalars(select(Product).where(Product.is_visible.is_(True))))
    offers = list(db.scalars(select(Offer).where(Offer.active.is_(True), Offer.approved.is_(True))))
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
