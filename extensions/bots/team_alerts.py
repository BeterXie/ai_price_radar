"""Select currently available Team offers for bot notifications."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop
from app.services.catalog import _base_public_offer_query, _fresh_cutoff
from app.services.team_rules import BEIJING, TEAM_PRICE_LIMIT, TEAM_HEAD_PRICE_LIMIT, is_head_car_title, is_team_account_title, team_title_ends_at


@dataclass(frozen=True, slots=True)
class TeamLowPriceOffer:
    offer_id: int
    product_name: str
    shop_name: str
    price: Decimal
    product_url: str
    ends_at: datetime | None = None
    is_head_car: bool = False


def collect_team_low_price_offers(db: Session, snapshot: CatalogSnapshot, *, now: datetime | None = None) -> list[TeamLowPriceOffer]:
    if snapshot.published_at is None:
        return []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    stmt = (
        _base_public_offer_query(
            db,
            snapshot=snapshot,
            cutoff=_fresh_cutoff(),
            include_details=False,
        )
        .join(Product, Offer.product_id == Product.id)
        .where(
            Product.is_visible.is_(True),
            # Business is the canonical Team product. Access-service is kept
            # because some Team accounts are classified there for 2FA/Gmail.
            Product.slug.in_(("chatgpt-business", "chatgpt-access-service")),
            Shop.status != "closed",
            Offer.currency.in_(("CNY", "RMB")),
            Offer.stock_status == "in_stock",
            or_(Offer.stock_count.is_(None), Offer.stock_count > 0),
            Offer.price > 0,
            Offer.price <= TEAM_HEAD_PRICE_LIMIT,
        )
        .with_only_columns(Offer.id, RawProduct.original_name, Shop.name.label('shop_name'), Offer.price,
                           Offer.source_url, RawProduct.source_url.label('raw_source_url'), Offer.observed_at,
                           maintain_column_froms=True)
        .order_by(Offer.price, Offer.id)
    )
    result = []
    for offer in db.execute(stmt):
        if not is_team_account_title(offer.original_name):
            continue
        head_car = is_head_car_title(offer.original_name)
        if offer.price > (TEAM_HEAD_PRICE_LIMIT if head_car else TEAM_PRICE_LIMIT):
            continue
        ends_at = team_title_ends_at(offer.original_name, observed_at=offer.observed_at)
        if ends_at is None or ends_at <= now:
            continue
        result.append(TeamLowPriceOffer(
            offer_id=offer.id,
            product_name=offer.original_name,
            shop_name=offer.shop_name,
            price=offer.price,
            product_url=offer.source_url or offer.raw_source_url,
            ends_at=ends_at,
            is_head_car=head_car,
        ))
    return result
