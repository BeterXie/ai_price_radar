"""Brand-scoped publishing. All product/catalog routes retain their shared contract."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RelayStation, SystemSetting, utcnow
from ..schemas import AdSlotCreate, AdSlotOut, AdSlotUpdate, RelayStationListOut
from ..security import require_admin
from ..services.promo import ad_slot_public, is_ad_live, public_link, relay_station_public
from ..site_models import SiteAd, SiteArticle, SiteRelay

SITES = {
    "pricememo": {"name": "PriceMemo", "url": "https://ai.pricememo.cn", "aliases": ["pricememo.cn"]},
    "aiprice": {"name": "AIPrice", "url": "https://aiprice.si", "aliases": []},
    "aisi": {"name": "AISI Plus", "url": "https://aisi.plus", "aliases": []},
    "pricein": {"name": "PriceIn", "url": "https://pricein.cc", "aliases": []},
    "openprice": {"name": "OpenPrice", "url": "https://openprice.in", "aliases": []},
}


def site_id(site_id: str) -> str:
    if site_id not in SITES:
        raise HTTPException(404, "Unknown site")
    return site_id


router = APIRouter(prefix="/api/v1/sites/{site_id}", tags=["sites"])
admin_router = APIRouter(prefix="/api/v1/admin/sites", dependencies=[Depends(require_admin)], tags=["site publishing"])


class SiteSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    notice_title: str = Field(default="", max_length=120)
    notice_content: str = Field(default="", max_length=2000)
    notice_link: str = Field(default="", max_length=1000)
    advertise_enabled: bool = False
    ad_slots_enabled: bool = True
    relay_hub_enabled: bool = True
    google_verification: str = Field(default="", max_length=200)
    bing_verification: str = Field(default="", max_length=200)
    baidu_verification: str = Field(default="", max_length=200)
    ga_measurement_id: str = Field(default="", max_length=40, pattern=r"^(G-[A-Z0-9]+)?$")
    baidu_analytics_id: str = Field(default="", pattern=r"^([a-f0-9]{32})?$")

    @field_validator("notice_link")
    @classmethod
    def safe_link(cls, value: str) -> str:
        if value and not public_link(value):
            raise ValueError("Use a local path or public HTTPS URL")
        return value


def read_settings(db: Session, key: str) -> SiteSettings:
    row = db.get(SystemSetting, f"site:{key}:settings")
    if row:
        return SiteSettings.model_validate_json(row.value)
    return SiteSettings(baidu_analytics_id="0abf0f3c54963dc5874f6a4ebcbfaf37") if key == "pricememo" else SiteSettings()


@admin_router.get("")
def list_sites() -> list[dict]:
    return [{"id": key, **value} for key, value in SITES.items()]


@router.get("/settings")
@admin_router.get("/{site_id}/settings")
def get_settings(key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    settings = read_settings(db, key)
    return {**settings.model_dump(), "configured": db.get(SystemSetting, f"site:{key}:settings") is not None}


@admin_router.put("/{site_id}/settings")
def save_settings(payload: SiteSettings, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    setting_key = f"site:{key}:settings"
    row = db.get(SystemSetting, setting_key)
    if row is None:
        row = SystemSetting(key=setting_key)
        db.add(row)
    row.value = payload.model_dump_json()
    db.commit()
    return {**payload.model_dump(), "configured": True}


class ArticleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=80)
    author: str = Field(default="", max_length=100)
    markdown: str = Field(min_length=1, max_length=200000)
    seo_title: str = Field(default="", max_length=160)
    seo_description: str = Field(default="", max_length=280)
    status: Literal["draft", "published"] = "draft"


def article_out(row: SiteArticle, *, body: bool = True) -> dict:
    result = {name: getattr(row, name) for name in (
        "id", "site_id", "slug", "title", "summary", "category", "author", "seo_title",
        "seo_description", "status", "published_at", "updated_at",
    )}
    if body:
        result["markdown"] = row.markdown
    return result


def find_article(db: Session, key: str, article_id: int) -> SiteArticle:
    row = db.scalar(select(SiteArticle).where(SiteArticle.site_id == key, SiteArticle.id == article_id))
    if row is None:
        raise HTTPException(404, "Article not found")
    return row


@router.get("/articles")
def public_articles(key: str = Depends(site_id), db: Session = Depends(get_db),
                    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100)) -> dict:
    query = select(SiteArticle).where(SiteArticle.site_id == key, SiteArticle.status == "published")
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(SiteArticle.published_at.desc(), SiteArticle.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {"items": [article_out(row, body=False) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/articles/{slug}")
def public_article(slug: str, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(SiteArticle).where(SiteArticle.site_id == key, SiteArticle.slug == slug, SiteArticle.status == "published"))
    if row is None:
        raise HTTPException(404, "Article not found")
    return article_out(row)


@admin_router.get("/{site_id}/articles")
def admin_articles(key: str = Depends(site_id), db: Session = Depends(get_db),
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)) -> dict:
    query = select(SiteArticle).where(SiteArticle.site_id == key)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(SiteArticle.updated_at.desc(), SiteArticle.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {"items": [article_out(row, body=False) for row in rows], "total": total, "page": page, "page_size": page_size}


@admin_router.get("/{site_id}/articles/{article_id}")
def admin_article(article_id: int, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    return article_out(find_article(db, key, article_id))


def write_article(db: Session, row: SiteArticle, payload: ArticleInput) -> dict:
    for name, value in payload.model_dump().items():
        setattr(row, name, value)
    if row.status == "published" and row.published_at is None:
        row.published_at = utcnow()
    row.updated_at = utcnow()
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This article slug already exists on this site") from None
    return article_out(row)


@admin_router.post("/{site_id}/articles", status_code=201)
def create_article(payload: ArticleInput, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    return write_article(db, SiteArticle(site_id=key), payload)


@admin_router.put("/{site_id}/articles/{article_id}")
def update_article(article_id: int, payload: ArticleInput, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    return write_article(db, find_article(db, key, article_id), payload)


class RelayPublication(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tagline: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=20000)
    link_url: str = Field(default="", max_length=1000)
    sort_order: int = Field(default=100, ge=0, le=100000)
    is_enabled: bool = True
    is_sponsored: bool = False

    @field_validator("link_url")
    @classmethod
    def safe_link(cls, value: str) -> str:
        from ..services.source_platform import public_https_url_or_empty
        if value and not public_https_url_or_empty(value):
            raise ValueError("Use a public HTTPS URL")
        return value


@admin_router.get("/{site_id}/relays")
def relay_publications(key: str = Depends(site_id), db: Session = Depends(get_db)) -> list[dict]:
    publications = {row.station_id: row for row in db.scalars(select(SiteRelay).where(SiteRelay.site_id == key))}
    result = []
    for station in db.scalars(select(RelayStation).order_by(RelayStation.name, RelayStation.id)):
        row = publications.get(station.id)
        result.append({"station_id": station.id, "name": station.name, "url": station.url,
                       "approved": station.review_status == "approved" and station.is_enabled,
                       "publication": ({name: getattr(row, name) for name in RelayPublication.model_fields} if row else None),
                       "click_count": row.click_count if row else 0})
    return result


@admin_router.put("/{site_id}/relays/{station_id}")
def save_relay_publication(station_id: int, payload: RelayPublication, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    if key == "pricememo":
        raise HTTPException(409, "Manage PriceMemo relays in the existing relay catalog")
    if db.get(RelayStation, station_id) is None:
        raise HTTPException(404, "Relay not found")
    row = db.get(SiteRelay, (key, station_id)) or SiteRelay(site_id=key, station_id=station_id)
    for name, value in payload.model_dump().items():
        setattr(row, name, value)
    db.add(row)
    db.commit()
    return payload.model_dump()


@router.get("/relays", response_model=RelayStationListOut)
def site_relays(key: str = Depends(site_id), db: Session = Depends(get_db)) -> RelayStationListOut:
    if key == "pricememo":
        from .public import public_relay_stations
        return public_relay_stations(db)
    if not read_settings(db, key).relay_hub_enabled:
        return RelayStationListOut(items=[], total=0, enabled=False)
    rows = db.execute(select(SiteRelay, RelayStation).join(RelayStation, RelayStation.id == SiteRelay.station_id).where(
        SiteRelay.site_id == key, SiteRelay.is_enabled.is_(True), RelayStation.is_enabled.is_(True), RelayStation.review_status == "approved",
    ).order_by(SiteRelay.is_sponsored.desc(), SiteRelay.sort_order, SiteRelay.station_id))
    items = []
    for publication, station in rows:
        item = relay_station_public(station, db)
        item.tagline = publication.tagline or item.tagline
        item.description = publication.description or item.description
        item.url = public_link(publication.link_url) or item.url
        item.is_sponsored = publication.is_sponsored
        item.click_count = publication.click_count
        items.append(item)
    return RelayStationListOut(items=items, total=len(items), enabled=True)


@router.post("/relays/{station_id}/click")
def relay_click(station_id: int, request: Request, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    from .public import _enforce_client_rate_limit
    row = db.get(SiteRelay, (key, station_id))
    station = db.get(RelayStation, station_id)
    if not row or not row.is_enabled or not station or not station.is_enabled or station.review_status != "approved" or not read_settings(db, key).relay_hub_enabled:
        raise HTTPException(404, "Relay not found")
    _enforce_client_rate_limit(request, db, namespace=f"site-relay:{key}:{station_id}", max_requests=5, window_seconds=60, detail="Too many clicks")
    db.execute(update(SiteRelay).where(SiteRelay.site_id == key, SiteRelay.station_id == station_id).values(click_count=SiteRelay.click_count + 1))
    db.commit()
    return {"status": "ok", "click_count": row.click_count}


@router.get("/ads")
def site_ads(key: str = Depends(site_id), db: Session = Depends(get_db), placement: str = "", limit: int = Query(6, ge=1, le=20)) -> dict:
    if key == "pricememo":
        from ..services.promo import list_live_ad_slots, setting_enabled, AD_SLOTS_ENABLED_KEY
        enabled = setting_enabled(db, AD_SLOTS_ENABLED_KEY)
        return {"items": list_live_ad_slots(db, placement=placement, limit=limit) if enabled else [], "enabled": enabled}
    enabled = read_settings(db, key).ad_slots_enabled
    query = select(SiteAd).where(SiteAd.site_id == key, SiteAd.is_enabled.is_(True))
    if placement:
        query = query.where(SiteAd.placement == placement)
    items = [ad_slot_public(row) for row in db.scalars(query.order_by(SiteAd.sort_order, SiteAd.id)) if is_ad_live(row)] if enabled else []
    return {"items": items[:limit], "enabled": enabled}


@admin_router.get("/{site_id}/ads", response_model=list[AdSlotOut])
def admin_ads(key: str = Depends(site_id), db: Session = Depends(get_db)):
    return list(db.scalars(select(SiteAd).where(SiteAd.site_id == key).order_by(SiteAd.sort_order, SiteAd.id)))


@admin_router.post("/{site_id}/ads", response_model=AdSlotOut, status_code=201)
def create_ad(payload: AdSlotCreate, key: str = Depends(site_id), db: Session = Depends(get_db)):
    if key == "pricememo":
        raise HTTPException(409, "Manage PriceMemo ads in the existing ad catalog")
    row = SiteAd(site_id=key, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@admin_router.patch("/{site_id}/ads/{ad_id}", response_model=AdSlotOut)
def update_ad(ad_id: int, payload: AdSlotUpdate, key: str = Depends(site_id), db: Session = Depends(get_db)):
    row = db.scalar(select(SiteAd).where(SiteAd.site_id == key, SiteAd.id == ad_id))
    if row is None:
        raise HTTPException(404, "Ad not found")
    values = {name: getattr(row, name) for name in AdSlotCreate.model_fields}
    values.update(payload.model_dump(exclude_unset=True, exclude_none=True, exclude={"clear_schedule"}))
    if payload.clear_schedule:
        values.update(starts_at=None, ends_at=None)
    try:
        validated = AdSlotCreate.model_validate(values)
    except ValidationError:
        raise HTTPException(422, "Invalid ad settings") from None
    for name, value in validated.model_dump().items():
        setattr(row, name, value)
    db.commit()
    db.refresh(row)
    return row


@router.post("/ads/{ad_id}/click")
def ad_click(ad_id: int, request: Request, key: str = Depends(site_id), db: Session = Depends(get_db)) -> dict:
    from .public import _enforce_client_rate_limit
    row = db.scalar(select(SiteAd).where(SiteAd.site_id == key, SiteAd.id == ad_id))
    if row is None or not is_ad_live(row) or not read_settings(db, key).ad_slots_enabled:
        raise HTTPException(404, "Ad not found")
    _enforce_client_rate_limit(request, db, namespace=f"site-ad:{key}:{ad_id}", max_requests=5, window_seconds=60, detail="Too many clicks")
    db.execute(update(SiteAd).where(SiteAd.site_id == key, SiteAd.id == ad_id).values(click_count=SiteAd.click_count + 1))
    db.commit()
    return {"status": "ok", "click_count": row.click_count}
