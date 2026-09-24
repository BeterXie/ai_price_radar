"""Ad slots (广告栏位) and relay stations (中转站).

Both are admin-managed catalogs that live outside the crawled offer snapshot.
Public readers only ever see enabled rows, and every outbound link is
re-validated at read time so a legacy unsafe value can never reach a page.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdSlot, RelayStation, SystemSetting
from ..schemas import AD_PLACEMENTS, AdSlotPublic, RelayStationPublic
from .source_platform import public_https_url_or_empty

AD_SLOTS_ENABLED_KEY = "ad_slots_enabled"
RELAY_HUB_ENABLED_KEY = "relay_hub_enabled"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def setting_enabled(db: Session, key: str, default: bool = True) -> bool:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting or not setting.value:
        return default
    return setting.value.strip().lower() in ("true", "1", "yes", "on")


def public_link(value: str) -> str:
    """Internal paths stay as-is; everything else must be a public HTTPS URL."""
    cleaned = str(value or "").strip()
    if cleaned.startswith("/") and not cleaned.startswith("//") and "\\" not in cleaned:
        return cleaned
    return public_https_url_or_empty(cleaned)


def is_ad_live(slot: AdSlot, now: datetime | None = None) -> bool:
    if not slot.is_enabled:
        return False
    moment = now or _utcnow()
    starts_at = _as_utc(slot.starts_at)
    ends_at = _as_utc(slot.ends_at)
    if starts_at is not None and starts_at > moment:
        return False
    if ends_at is not None and ends_at < moment:
        return False
    return True


def ad_slot_public(slot: AdSlot) -> AdSlotPublic:
    return AdSlotPublic(
        id=slot.id,
        placement=slot.placement,
        title=slot.title,
        description=slot.description or "",
        sponsor_name=slot.sponsor_name or "",
        badge=(slot.badge or "广告").strip() or "广告",
        cta_text=(slot.cta_text or "了解详情").strip() or "了解详情",
        link_url=public_link(slot.link_url),
        image_url=public_link(slot.image_url),
    )


def list_live_ad_slots(db: Session, *, placement: str = "", limit: int = 6) -> list[AdSlotPublic]:
    stmt = select(AdSlot).where(AdSlot.is_enabled.is_(True))
    if placement:
        if placement not in AD_PLACEMENTS:
            return []
        stmt = stmt.where(AdSlot.placement == placement)
    stmt = stmt.order_by(AdSlot.sort_order.asc(), AdSlot.id.asc())
    now = _utcnow()
    items: list[AdSlotPublic] = []
    for slot in db.scalars(stmt):
        if not is_ad_live(slot, now):
            continue
        items.append(ad_slot_public(slot))
        if len(items) >= limit:
            break
    return items


def relay_station_public(station: RelayStation) -> RelayStationPublic:
    return RelayStationPublic(
        id=station.id,
        name=station.name,
        url=public_https_url_or_empty(station.url),
        tagline=station.tagline or "",
        description=station.description or "",
        supported_models=list(station.supported_models or []),
        price_note=station.price_note or "",
        billing_note=station.billing_note or "",
        tags=list(station.tags or []),
        is_sponsored=bool(station.is_sponsored),
        click_count=int(station.click_count or 0),
        updated_at=station.updated_at,
    )


def list_enabled_relay_stations(db: Session) -> list[RelayStationPublic]:
    stmt = (
        select(RelayStation)
        .where(RelayStation.is_enabled.is_(True))
        .order_by(RelayStation.is_sponsored.desc(), RelayStation.sort_order.asc(), RelayStation.id.asc())
    )
    return [relay_station_public(station) for station in db.scalars(stmt)]


def count_enabled_relay_stations(db: Session) -> int:
    from sqlalchemy import func

    return int(db.scalar(select(func.count(RelayStation.id)).where(RelayStation.is_enabled.is_(True))) or 0)
