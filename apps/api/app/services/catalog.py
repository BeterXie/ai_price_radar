from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from statistics import median
from typing import Any

from sqlalchemy import case, not_, or_, select
from sqlalchemy.orm import Session, contains_eager

from ..core.config import get_settings
from ..models import CatalogSnapshot, Offer, OfferHistory, Product, RawProduct, Shop
from ..schemas import (
    DeliveryPriceSummary,
    OfferGroupPublic,
    OfferPublic,
    PricePoint,
    ProductCard,
    ProductDetail,
    ShopDetail,
)


DEFAULT_OFFER_PAGE_SIZE = 30


@dataclass(frozen=True, slots=True)
class OfferFilters:
    delivery_type: str = ""
    service_period: str = ""
    warranty: str = ""
    auto_delivery: bool | None = None
    updated_within_hours: int | None = None
    comparable: bool | None = None
    exclude: str = ""
    in_stock: bool = False
    min_price: Decimal | None = None
    max_price: Decimal | None = None


class _DescriptionParser(HTMLParser):
    block_tags = {"br", "div", "li", "p", "section", "table", "tr"}
    ignored_tags = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        elif self.ignored_depth == 0 and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored_tags:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        elif self.ignored_depth == 0 and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)


def _plain_text(value: Any, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _DescriptionParser()
    parser.feed(value)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)[:limit]


def _raw_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return result if result > 0 else None


def _fresh_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=get_settings().stale_offer_hours)


def get_current_snapshot(db: Session) -> CatalogSnapshot | None:
    return db.scalar(
        select(CatalogSnapshot)
        .where(CatalogSnapshot.published_at.is_not(None))
        .order_by(CatalogSnapshot.id.desc())
        .limit(1)
    )


def _snapshot_for_query(db: Session, snapshot_id: int | None = None) -> CatalogSnapshot | None:
    if snapshot_id is not None:
        snapshot = db.scalar(
            select(CatalogSnapshot).where(
                CatalogSnapshot.id == snapshot_id,
                CatalogSnapshot.published_at.is_not(None),
            )
        )
        if snapshot is not None:
            return snapshot
    return get_current_snapshot(db)


def _base_public_offer_query(
    db: Session,
    *,
    include_details: bool = True,
    snapshot: CatalogSnapshot | None = None,
):
    snapshot = snapshot or get_current_snapshot(db)
    stmt = (
        select(Offer)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(RawProduct, Offer.raw_product_id == RawProduct.id)
        .where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Offer.product_id.is_not(None),
            Shop.is_visible.is_(True),
            Offer.observed_at >= _fresh_cutoff(),
        )
    )
    if snapshot is not None:
        stmt = stmt.where(Offer.snapshot_id == snapshot.id)
    if include_details:
        stmt = stmt.options(contains_eager(Offer.shop), contains_eager(Offer.raw_product))
    return stmt


def _apply_offer_filters(stmt, filters: OfferFilters):
    if filters.delivery_type:
        stmt = stmt.where(Offer.delivery_type == filters.delivery_type)
    if filters.service_period:
        stmt = stmt.where(Offer.service_period == filters.service_period)
    if filters.warranty:
        stmt = stmt.where(Offer.warranty == filters.warranty)
    if filters.auto_delivery is not None:
        stmt = stmt.where(Offer.auto_delivery == filters.auto_delivery)
    if filters.updated_within_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=filters.updated_within_hours)
        stmt = stmt.where(Offer.observed_at >= cutoff)
    if filters.comparable is not None:
        stmt = stmt.where(Offer.is_comparable == filters.comparable)
    if filters.in_stock:
        stmt = stmt.where(Offer.stock_status == "in_stock")
    if filters.min_price is not None:
        stmt = stmt.where(Offer.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Offer.price <= filters.max_price)
    for term in [value.strip() for value in filters.exclude.split(",") if value.strip()]:
        stmt = stmt.where(not_(RawProduct.original_name.ilike(f"%{term}%")))
    return stmt


def _offer_ordering():
    return (
        case((Offer.stock_status == "in_stock", 0), else_=1),
        case((Offer.price.is_(None), 1), else_=0),
        Offer.price.asc(),
        Offer.observed_at.desc(),
        Offer.id.asc(),
    )


def _offer_sort_key(offer: Offer):
    return (
        offer.stock_status != "in_stock",
        offer.price is None,
        offer.price or Decimal("999999"),
        -offer.observed_at.timestamp(),
        offer.id,
    )


def _low_price_warning(price: Decimal | None, median_price: Decimal | None) -> str | None:
    if price is None or price <= 0:
        return None
    if price < Decimal("1"):
        return "价格低于 ¥1，请核对是否为体验、余额或受限商品。"
    if median_price and median_price > 0 and price < median_price * Decimal("0.4"):
        percentage = max(1, round((Decimal("1") - price / median_price) * 100))
        return f"该报价比同交付形态中位价低约 {percentage}%，请重点核对。"
    return None


def _offer_public(
    offer: Offer,
    *,
    include_description: bool = False,
    median_price: Decimal | None = None,
) -> OfferPublic:
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    raw_description = raw_json.get("description")
    description = _plain_text(raw_description) if include_description else ""
    return OfferPublic(
        id=offer.id,
        shop_token=offer.shop.token,
        shop_name=offer.shop.name or offer.shop.token,
        original_name=offer.raw_product.original_name,
        original_category=_plain_text(offer.raw_product.original_category, 300),
        original_description=description if include_description else "",
        description_available=isinstance(raw_description, str) and bool(raw_description.strip()),
        goods_type=_plain_text(raw_json.get("goods_type"), 120),
        price=offer.price,
        market_price=_raw_decimal(raw_json.get("market_price")),
        currency=offer.currency,
        stock_count=offer.stock_count,
        stock_status=offer.stock_status,
        auto_delivery=offer.auto_delivery,
        tags=offer.tags or [],
        risk_flags=offer.risk_flags or [],
        delivery_type=offer.delivery_type or "unknown",
        is_comparable=bool(offer.is_comparable),
        service_period=offer.service_period or "unknown",
        warranty=offer.warranty or "unknown",
        use_scenarios=offer.use_scenarios or [],
        item_fingerprint=offer.item_fingerprint or f"offer-{offer.id}",
        low_price_warning=_low_price_warning(offer.price, median_price),
        source_url=offer.source_url,
        first_seen_at=offer.raw_product.first_seen_at,
        last_seen_at=offer.raw_product.last_seen_at,
        observed_at=offer.observed_at,
    )


def _median_prices(offers: list[Offer]) -> dict[str, Decimal]:
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for offer in offers:
        if offer.stock_status == "in_stock" and offer.price is not None and offer.price > 0:
            grouped[offer.delivery_type or "unknown"].append(offer.price)
    return {delivery_type: Decimal(str(median(values))) for delivery_type, values in grouped.items() if values}


def _group_offers(offers: list[Offer]) -> list[tuple[str, list[Offer]]]:
    grouped: dict[str, list[Offer]] = defaultdict(list)
    for offer in offers:
        grouped[offer.item_fingerprint or f"offer-{offer.id}"].append(offer)
    groups = [(fingerprint, sorted(group, key=_offer_sort_key)) for fingerprint, group in grouped.items()]
    groups.sort(key=lambda item: _offer_sort_key(item[1][0]))
    return groups


def get_product_group_page(
    db: Session,
    product_id: int,
    *,
    offset: int,
    limit: int,
    filters: OfferFilters,
    snapshot: CatalogSnapshot | None = None,
) -> tuple[list[OfferGroupPublic], int, int]:
    snapshot = snapshot or get_current_snapshot(db)
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .where(Offer.product_id == product_id),
        filters,
    )
    offers = list(db.scalars(stmt).unique())
    grouped = _group_offers(offers)
    selected = grouped[offset:offset + limit]
    representative_ids = [group[0].id for _, group in selected]
    representatives: dict[int, Offer] = {}
    if representative_ids:
        detail_stmt = _base_public_offer_query(db, snapshot=snapshot).where(Offer.id.in_(representative_ids))
        representatives = {offer.id: offer for offer in db.scalars(detail_stmt).unique()}
    medians = _median_prices(offers)

    items: list[OfferGroupPublic] = []
    for fingerprint, group in selected:
        representative = representatives[group[0].id]
        in_stock = [offer for offer in group if offer.stock_status == "in_stock"]
        prices = [offer.price for offer in in_stock if offer.price is not None and offer.price > 0]
        items.append(OfferGroupPublic(
            fingerprint=fingerprint,
            representative=_offer_public(
                representative,
                median_price=medians.get(representative.delivery_type or "unknown"),
            ),
            offer_count=len(group),
            shop_count=len({offer.shop_id for offer in group}),
            in_stock_count=len(in_stock),
            lowest_price=min(prices, default=None),
            highest_price=max(prices, default=None),
            latest_observed_at=max((offer.observed_at for offer in group), default=None),
        ))
    return items, len(grouped), len(offers)


def list_product_cards(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_type: str = "",
    tag: str = "",
    filters: OfferFilters = OfferFilters(),
    sort: str = "price",
    snapshot_id: int | None = None,
) -> list[ProductCard]:
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = (
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .options(contains_eager(Offer.product))
        .where(Product.is_visible.is_(True))
    )
    stmt = _apply_offer_filters(stmt, filters)
    if platform:
        stmt = stmt.where(Product.platform == platform)
    if product_slug:
        stmt = stmt.where(Product.slug == product_slug)
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(
            Product.display_name.ilike(pattern),
            Product.slug.ilike(pattern),
            RawProduct.original_name.ilike(pattern),
        ))

    offers = list(db.scalars(stmt).unique())
    grouped: dict[int, list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.product_id is None:
            continue
        if tag and tag not in (offer.tags or []):
            continue
        grouped[offer.product_id].append(offer)

    cards: list[ProductCard] = []
    for group in grouped.values():
        product = group[0].product
        if product is None:
            continue
        in_stock = [x for x in group if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
        comparable = [x for x in in_stock if x.is_comparable]
        all_tags = sorted({tag_value for offer in group for tag_value in (offer.tags or [])})
        cards.append(ProductCard(
            slug=product.slug,
            platform=product.platform,
            display_name=product.display_name,
            subtitle=product.subtitle,
            product_type=product.product_type,
            lowest_price=min((x.price for x in comparable), default=None),
            related_lowest_price=min((x.price for x in in_stock), default=None),
            offer_count=len(group),
            in_stock_count=len(in_stock),
            comparable_offer_count=sum(1 for x in group if x.is_comparable),
            last_updated_at=max((x.observed_at for x in group), default=None),
            tags=all_tags[:8],
        ))

    if sort == "updated":
        cards.sort(key=lambda x: x.last_updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    elif sort == "offers":
        cards.sort(key=lambda x: (x.in_stock_count, x.offer_count), reverse=True)
    elif sort == "price_desc":
        cards.sort(key=lambda x: (x.lowest_price is None, -(x.lowest_price or Decimal("0")), -x.in_stock_count))
    else:
        cards.sort(key=lambda x: (x.lowest_price is None, x.lowest_price or Decimal("999999"), -x.in_stock_count))
    return cards


def get_product_detail(
    db: Session,
    slug: str,
    *,
    filters: OfferFilters = OfferFilters(comparable=True),
    snapshot_id: int | None = None,
) -> ProductDetail | None:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product is None:
        return None
    snapshot = _snapshot_for_query(db, snapshot_id)
    offers = list(db.scalars(
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .where(Offer.product_id == product.id)
    ).unique())
    in_stock = [x for x in offers if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
    comparable_in_stock = [x for x in in_stock if x.is_comparable]

    history_stmt = (
        select(OfferHistory)
        .join(Offer, OfferHistory.offer_id == Offer.id)
        .where(Offer.product_id == product.id)
        .order_by(OfferHistory.observed_at.desc())
        .limit(120)
    )
    history = list(db.scalars(history_stmt))
    history.reverse()
    all_tags = sorted({tag for offer in offers for tag in (offer.tags or [])})

    breakdown: list[DeliveryPriceSummary] = []
    delivery_groups: dict[str, list[Offer]] = defaultdict(list)
    for offer in offers:
        delivery_groups[offer.delivery_type or "unknown"].append(offer)
    for delivery_type, group in delivery_groups.items():
        group_stock = [x for x in group if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
        breakdown.append(DeliveryPriceSummary(
            delivery_type=delivery_type,
            lowest_price=min((x.price for x in group_stock), default=None),
            offer_count=len(group),
            in_stock_count=len(group_stock),
        ))
    breakdown.sort(key=lambda item: (item.lowest_price is None, item.lowest_price or Decimal("999999")))

    offer_groups, group_count, _ = get_product_group_page(
        db,
        product.id,
        offset=0,
        limit=DEFAULT_OFFER_PAGE_SIZE,
        filters=filters,
        snapshot=snapshot,
    )
    return ProductDetail(
        slug=product.slug,
        platform=product.platform,
        display_name=product.display_name,
        subtitle=product.subtitle,
        description=product.description,
        product_type=product.product_type,
        lowest_price=min((x.price for x in comparable_in_stock), default=None),
        related_lowest_price=min((x.price for x in in_stock), default=None),
        highest_price=max((x.price for x in comparable_in_stock), default=None),
        offer_count=len(offers),
        in_stock_count=len(in_stock),
        comparable_offer_count=sum(1 for x in offers if x.is_comparable),
        offer_group_count=group_count,
        last_updated_at=max((x.observed_at for x in offers), default=None),
        tags=all_tags,
        price_breakdown=breakdown,
        snapshot_id=snapshot.id if snapshot else None,
        snapshot_at=snapshot.published_at if snapshot else None,
        offer_groups=offer_groups,
        history=[PricePoint(observed_at=x.observed_at, price=x.price, stock_status=x.stock_status) for x in history],
    )


def get_product_offer_page(
    db: Session,
    slug: str,
    *,
    offset: int,
    limit: int,
    snapshot_id: int | None = None,
) -> list[OfferPublic] | None:
    product_id = db.scalar(select(Product.id).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product_id is None:
        return None
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = (
        _base_public_offer_query(db, snapshot=snapshot)
        .where(Offer.product_id == product_id)
        .order_by(*_offer_ordering())
        .offset(offset)
        .limit(limit)
    )
    return [_offer_public(offer) for offer in db.scalars(stmt).unique()]


def get_group_offers(
    db: Session,
    slug: str,
    fingerprint: str,
    *,
    snapshot_id: int | None = None,
) -> list[OfferPublic] | None:
    product_id = db.scalar(select(Product.id).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product_id is None:
        return None
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = (
        _base_public_offer_query(db, snapshot=snapshot)
        .where(
            Offer.product_id == product_id,
            Offer.item_fingerprint == fingerprint,
        )
        .order_by(*_offer_ordering())
    )
    offers = list(db.scalars(stmt).unique())
    medians = _median_prices(offers)
    return [_offer_public(offer, median_price=medians.get(offer.delivery_type or "unknown")) for offer in offers]


def get_offer_description(db: Session, offer_id: int) -> str | None:
    offer = db.scalar(_base_public_offer_query(db).where(Offer.id == offer_id))
    if offer is None:
        return None
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    return _plain_text(raw_json.get("description"))


def get_shop_detail(db: Session, token: str) -> ShopDetail | None:
    shop = db.scalar(select(Shop).where(Shop.token == token, Shop.is_visible.is_(True)))
    if shop is None:
        return None
    offers = list(db.scalars(
        _base_public_offer_query(db)
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.shop_id == shop.id, Product.is_visible.is_(True))
        .order_by(*_offer_ordering())
    ).unique())
    medians = _median_prices(offers)
    return ShopDetail(
        token=shop.token,
        name=shop.name or shop.token,
        source_url=shop.source_url,
        platform=shop.platform,
        status=shop.status,
        first_seen_at=shop.first_seen_at,
        last_success_at=shop.last_success_at,
        last_seen_at=shop.last_seen_at,
        consecutive_failures=shop.consecutive_failures,
        offer_count=len(offers),
        offers=[_offer_public(x, median_price=medians.get(x.delivery_type or "unknown")) for x in offers],
    )
