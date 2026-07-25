from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Offer, Product, Report, ScanRun, Shop
from ..schemas import AdminOfferUpdate, AdminReportUpdate, AdminStats, ReportOut
from ..security import require_admin
from ..services.classifier import classify_product

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db)) -> AdminStats:
    last_scan = db.scalar(select(func.max(ScanRun.finished_at)))
    return AdminStats(
        shops=db.scalar(select(func.count()).select_from(Shop)) or 0,
        products=db.scalar(select(func.count()).select_from(Product)) or 0,
        offers=db.scalar(select(func.count()).select_from(Offer)) or 0,
        public_offers=db.scalar(select(func.count()).select_from(Offer).where(Offer.active.is_(True), Offer.approved.is_(True))) or 0,
        open_reports=db.scalar(select(func.count()).select_from(Report).where(Report.status == "open")) or 0,
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
    return list(db.scalars(select(Report).where(Report.status == status).order_by(Report.created_at.desc())))


@router.patch("/reports/{report_id}")
def update_report(report_id: int, payload: AdminReportUpdate, db: Session = Depends(get_db)) -> dict:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    report.status = payload.status
    db.commit()
    return {"ok": True, "id": report.id, "status": report.status}
