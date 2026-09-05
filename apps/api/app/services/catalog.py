from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from statistics import median
from typing import Any

from sqlalchemy import case, func, not_, or_, select
from sqlalchemy.orm import Session, contains_eager

from ..core.config import get_settings
from ..models import CatalogSnapshot, Offer, OfferHistory, Product, RawProduct, Shop
from ..schemas import (
    DeliveryPriceSummary,
    OfferGroupPublic,
    OfferPublic,
    PriceTrendPoint,
    ProductCard,
    ProductDetail,
    ProductHistoryResponse,
    ShopProduct,
    ShopDetail,
)
from .official_pricing import official_reference_for
from .pricing import MIN_TRUSTED_PRICE, is_trusted_price, low_price_warning, price_median
from .source_health import source_health
from .source_platform import (
    DISABLED_SOURCE_PLATFORMS,
    get_disabled_source_platforms,
    source_kind,
    source_kind_label,
    source_platform_label,
)


DEFAULT_OFFER_PAGE_SIZE = 30
PRICE_CURRENCY = "CNY"


@dataclass(frozen=True, slots=True)
class OfferFilters:
    source_platform: str = ""
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


def get_snapshot(db: Session, snapshot_id: int | None = None) -> CatalogSnapshot | None:
    return _snapshot_for_query(db, snapshot_id)


def _base_public_offer_query(
    db: Session,
    *,
    include_details: bool = True,
    snapshot: CatalogSnapshot | None = None,
):
    snapshot = snapshot or get_current_snapshot(db)
    disabled_platforms = get_disabled_source_platforms()
    conditions = [
        Offer.active.is_(True),
        Offer.approved.is_(True),
        Offer.product_id.is_not(None),
        Shop.is_visible.is_(True),
        Offer.observed_at >= _fresh_cutoff(),
    ]
    if disabled_platforms:
        conditions.append(Shop.platform.notin_(disabled_platforms))
    stmt = (
        select(Offer)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(RawProduct, Offer.raw_product_id == RawProduct.id)
        .where(*conditions)
    )
    if snapshot is not None:
        stmt = stmt.where(Offer.snapshot_id == snapshot.id)
    if include_details:
        stmt = stmt.options(contains_eager(Offer.shop), contains_eager(Offer.raw_product))
    return stmt


def _apply_offer_filters(stmt, filters: OfferFilters):
    if filters.source_platform:
        stmt = stmt.where(Shop.platform == filters.source_platform)
    if filters.delivery_type:
        stmt = stmt.where(Offer.delivery_type == filters.delivery_type)
    if filters.service_period:
        stmt = stmt.where(Offer.service_period == filters.service_period)
    if filters.warranty == "covered":
        stmt = stmt.where(Offer.warranty.notin_(("none", "unknown")))
    elif filters.warranty:
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
    if filters.min_price is not None or filters.max_price is not None:
        stmt = stmt.where(Offer.currency == PRICE_CURRENCY)
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
        case((Offer.currency == PRICE_CURRENCY, 0), else_=1),
        Offer.currency.asc(),
        case((Offer.price.is_(None), 1), else_=0),
        Offer.price.asc(),
        Offer.observed_at.desc(),
        Offer.id.asc(),
    )


def _offer_sort_key(offer: Offer):
    return (
        offer.stock_status != "in_stock",
        not offer.is_comparable,
        offer.currency != PRICE_CURRENCY,
        offer.currency,
        offer.price is None,
        offer.price is not None and offer.price < MIN_TRUSTED_PRICE,
        offer.price or Decimal("999999"),
        -offer.observed_at.timestamp(),
        offer.id,
    )


def _low_price_warning(price: Decimal | None, median_price: Decimal | None, currency: str) -> str | None:
    return low_price_warning(price, median_price, currency)


def _offer_public(
    offer: Offer,
    *,
    include_description: bool = False,
    median_price: Decimal | None = None,
) -> OfferPublic:
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    raw_description = raw_json.get("description")
    description = _plain_text(raw_description) if include_description else ""
    warning = _low_price_warning(offer.price, median_price, offer.currency)
    return OfferPublic(
        id=offer.id,
        shop_token=offer.shop.token,
        shop_name=offer.shop.name or offer.shop.token,
        source_platform=offer.shop.platform,
        source_platform_label=source_platform_label(offer.shop.platform),
        source_kind=source_kind(offer.shop.platform),
        source_kind_label=source_kind_label(source_kind(offer.shop.platform)),
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
        low_price_warning=warning,
        is_trusted_price=bool(offer.is_comparable) and is_trusted_price(offer.price, median_price),
        source_health=asdict(source_health(offer.shop)),
        source_url=offer.source_url,
        first_seen_at=offer.raw_product.first_seen_at,
        last_seen_at=offer.raw_product.last_seen_at,
        observed_at=offer.observed_at,
    )


def _median_key(offer: Offer) -> tuple[str, str]:
    return offer.delivery_type or "unknown", offer.currency or PRICE_CURRENCY


def _median_prices(offers: list[Offer], *, comparable_only: bool = False) -> dict[tuple[str, str], Decimal]:
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for offer in offers:
        if comparable_only and not offer.is_comparable:
            continue
        if offer.stock_status == "in_stock" and offer.price is not None and offer.price > 0:
            grouped[_median_key(offer)].append(offer.price)
    return {
        key: median_price
        for key, values in grouped.items()
        if (median_price := price_median(values)) is not None
    }


def _is_trusted_offer(offer: Offer, medians: dict[tuple[str, str], Decimal]) -> bool:
    return (
        offer.stock_status == "in_stock"
        and bool(offer.is_comparable)
        and is_trusted_price(offer.price, medians.get(_median_key(offer)))
    )


def _trusted_offer_sort_key(offer: Offer, medians: dict[tuple[str, str], Decimal] | None = None):
    return _offer_sort_key(offer)


def _group_offers(
    offers: list[Offer],
    medians: dict[tuple[str, str], Decimal] | None = None,
) -> list[tuple[str, list[Offer]]]:
    grouped: dict[str, list[Offer]] = defaultdict(list)
    for offer in offers:
        grouped[offer.item_fingerprint or f"offer-{offer.id}"].append(offer)
    groups = [
        (fingerprint, sorted(group, key=lambda offer: _trusted_offer_sort_key(offer, medians)))
        for fingerprint, group in grouped.items()
    ]
    groups.sort(key=lambda item: _trusted_offer_sort_key(item[1][0], medians))
    return groups


def _data_quality(offers: list[Offer], trusted: list[Offer], comparable: list[Offer]) -> tuple[int, str]:
    if not offers:
        return 0, "数据不足"
    source_count = len({offer.shop_id for offer in offers})
    comparable_count = len(comparable)
    trusted_ratio = len(trusted) / comparable_count if comparable_count else 0
    latest = max((offer.observed_at for offer in offers), default=None)
    freshness = 0
    if latest is not None:
        latest = latest if latest.tzinfo is not None else latest.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600)
        freshness = 30 if age_hours <= 6 else 22 if age_hours <= 24 else 12 if age_hours <= 72 else 0
    score = round(45 * trusted_ratio + min(25, source_count * 5) + freshness)
    score = max(0, min(100, score))
    label = "充足" if score >= 80 else "一般" if score >= 55 else "有限"
    return score, label


def _price_trend(
    db: Session,
    product_id: int,
    *,
    currency: str = PRICE_CURRENCY,
    source_platform: str = "",
    day_limit: int = 90,
) -> list[PriceTrendPoint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=day_limit)
    stmt = (
        select(OfferHistory, Offer)
        .join(Offer, OfferHistory.offer_id == Offer.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(
            Offer.product_id == product_id,
            Offer.approved.is_(True),
            Shop.is_visible.is_(True),
            OfferHistory.currency == currency,
            OfferHistory.observed_at >= cutoff,
        )
        .order_by(OfferHistory.observed_at.asc())
    )
    if source_platform:
        stmt = stmt.where(Shop.platform == source_platform)
    rows = db.execute(stmt).all()
    grouped: dict[datetime, list[tuple[OfferHistory, Offer]]] = defaultdict(list)
    for history, offer in rows:
        observed = history.observed_at
        observed = observed if observed.tzinfo is not None else observed.replace(tzinfo=timezone.utc)
        bucket = observed.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        grouped[bucket].append((history, offer))

    result: list[PriceTrendPoint] = []
    for bucket, records in sorted(grouped.items()):
        comparable_records = [
            (history, offer)
            for history, offer in records
            if offer.is_comparable and history.stock_status == "in_stock" and history.price is not None and history.price > 0
        ]
        delivery_prices: dict[str, list[Decimal]] = defaultdict(list)
        for history, offer in comparable_records:
            delivery_prices[offer.delivery_type or "unknown"].append(history.price)
        medians = {key: value for key, values in delivery_prices.items() if (value := price_median(values)) is not None}
        trusted_prices = [
            history.price
            for history, offer in comparable_records
            if is_trusted_price(history.price, medians.get(offer.delivery_type or "unknown"))
        ]
        all_prices = [history.price for history, _ in comparable_records if history.price is not None]
        result.append(PriceTrendPoint(
            bucket_at=bucket,
            price_currency=currency,
            trusted_lowest_price=min(trusted_prices, default=None),
            median_price=price_median(all_prices),
            in_stock_count=sum(1 for history, _ in records if history.stock_status == "in_stock"),
            observation_count=len(records),
        ))
    return result


def get_product_group_page(
    db: Session,
    product_id: int,
    *,
    offset: int,
    limit: int,
    filters: OfferFilters,
    snapshot: CatalogSnapshot | None = None,
) -> tuple[list[OfferGroupPublic], int, int]:
    product = db.get(Product, product_id)
    if product is None:
        return [], 0, 0
    snapshot = snapshot or get_current_snapshot(db)
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .where(Offer.product_id == product_id),
        filters,
    )
    offers = list(db.scalars(stmt).unique())
    medians = _median_prices(offers, comparable_only=True)
    grouped = _group_offers(offers, medians)
    selected = grouped[offset:offset + limit]
    representative_ids = [group[0].id for _, group in selected]
    representatives: dict[int, Offer] = {}
    if representative_ids:
        detail_stmt = _base_public_offer_query(db, snapshot=snapshot).where(Offer.id.in_(representative_ids))
        representatives = {offer.id: offer for offer in db.scalars(detail_stmt).unique()}
    medians = _median_prices(offers, comparable_only=True)

    items: list[OfferGroupPublic] = []
    for fingerprint, group in selected:
        representative = representatives[group[0].id]
        in_stock = [offer for offer in group if offer.stock_status == "in_stock"]
        trusted = [offer for offer in group if _is_trusted_offer(offer, medians)]
        prices = [offer.price for offer in trusted if offer.currency == PRICE_CURRENCY and offer.price is not None]
        if not prices:
            prices = [
                offer.price
                for offer in in_stock
                if offer.currency == PRICE_CURRENCY and offer.price is not None and offer.price >= MIN_TRUSTED_PRICE
            ] or [
                offer.price
                for offer in group
                if offer.currency == PRICE_CURRENCY and offer.price is not None
            ]
        items.append(OfferGroupPublic(
            product_slug=product.slug,
            product_name=product.display_name,
            fingerprint=fingerprint,
            representative=_offer_public(
                representative,
                median_price=medians.get(_median_key(representative)),
            ),
            offer_count=len(group),
            shop_count=len({offer.shop_id for offer in group}),
            in_stock_count=len(in_stock),
            price_currency=PRICE_CURRENCY,
            lowest_price=min(prices, default=None),
            highest_price=max(prices, default=None),
            latest_observed_at=max((offer.observed_at for offer in group), default=None),
        ))
    return items, len(grouped), len(offers)


def get_catalog_group_page(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    offset: int,
    limit: int,
    filters: OfferFilters,
    snapshot: CatalogSnapshot | None = None,
) -> tuple[list[OfferGroupPublic], int, int, int, int, int, datetime | None]:
    snapshot = snapshot or get_current_snapshot(db)
    stmt = (
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .where(Product.is_visible.is_(True))
    )
    if platform:
        stmt = stmt.where(Product.platform == platform)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(
            Product.display_name.ilike(pattern),
            Product.slug.ilike(pattern),
            RawProduct.original_name.ilike(pattern),
        ))
    if product_slug:
        stmt = stmt.where(Product.slug == product_slug)
    offers = list(db.scalars(_apply_offer_filters(stmt, filters)).unique())
    offers_by_product: dict[int, list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.product_id is not None:
            offers_by_product[offer.product_id].append(offer)
    medians_by_product = {
        scope_product_id: _median_prices(product_offers, comparable_only=True)
        for scope_product_id, product_offers in offers_by_product.items()
    }

    grouped: dict[tuple[int, str], list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.product_id is None:
            continue
        grouped[(offer.product_id, offer.item_fingerprint or f"offer-{offer.id}")].append(offer)
    groups = [
        (
            product_id,
            fingerprint,
            sorted(
                group,
                key=lambda offer: _trusted_offer_sort_key(offer, medians_by_product.get(product_id, {})),
            ),
        )
        for (product_id, fingerprint), group in grouped.items()
    ]
    groups.sort(
        key=lambda item: _trusted_offer_sort_key(item[2][0], medians_by_product.get(item[0], {}))
    )
    selected = groups[offset:offset + limit]

    representative_ids = [group[0].id for _, _, group in selected]
    representatives: dict[int, Offer] = {}
    if representative_ids:
        detail_stmt = _base_public_offer_query(db, snapshot=snapshot).where(Offer.id.in_(representative_ids))
        representatives = {offer.id: offer for offer in db.scalars(detail_stmt).unique()}
    product_ids = {product_id for product_id, _, _ in selected}
    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids)))
    } if product_ids else {}
    offers_by_product: dict[int, list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.product_id is not None:
            offers_by_product[offer.product_id].append(offer)
    medians_by_product = {
        scope_product_id: _median_prices(product_offers, comparable_only=True)
        for scope_product_id, product_offers in offers_by_product.items()
    }

    items: list[OfferGroupPublic] = []
    for product_id, fingerprint, group in selected:
        product = products.get(product_id)
        representative = representatives.get(group[0].id)
        if product is None or representative is None:
            continue
        in_stock = [offer for offer in group if offer.stock_status == "in_stock"]
        product_medians = medians_by_product.get(product_id, {})
        trusted = [offer for offer in group if _is_trusted_offer(offer, product_medians)]
        prices = [offer.price for offer in trusted if offer.currency == PRICE_CURRENCY and offer.price is not None]
        if not prices:
            prices = [
                offer.price
                for offer in in_stock
                if offer.currency == PRICE_CURRENCY and offer.price is not None and offer.price >= MIN_TRUSTED_PRICE
            ] or [
                offer.price
                for offer in group
                if offer.currency == PRICE_CURRENCY and offer.price is not None
            ]
        items.append(OfferGroupPublic(
            product_slug=product.slug,
            product_name=product.display_name,
            fingerprint=fingerprint,
            representative=_offer_public(
                representative,
                median_price=medians_by_product.get(product_id, {}).get(_median_key(representative)),
            ),
            offer_count=len(group),
            shop_count=len({offer.shop_id for offer in group}),
            in_stock_count=len(in_stock),
            price_currency=PRICE_CURRENCY,
            lowest_price=min(prices, default=None),
            highest_price=max(prices, default=None),
            latest_observed_at=max((offer.observed_at for offer in group), default=None),
        ))

    return (
        items,
        len(groups),
        len(offers),
        sum(1 for offer in offers if offer.stock_status == "in_stock"),
        sum(1 for offer in offers if offer.is_comparable),
        sum(
            1
            for product_id, product_offers in offers_by_product.items()
            for offer in product_offers
            if offer.currency == PRICE_CURRENCY and _is_trusted_offer(offer, medians_by_product.get(product_id, {}))
        ),
        max((offer.observed_at for offer in offers), default=None),
    )


def list_product_cards(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_type: str = "",
    tag: str = "",
    filters: OfferFilters = OfferFilters(),
    sort: str = "quality",
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
        price_scope = [x for x in in_stock if x.currency == PRICE_CURRENCY]
        comparable = [x for x in price_scope if x.is_comparable]
        medians = _median_prices(comparable, comparable_only=True)
        trusted = [x for x in comparable if _is_trusted_offer(x, medians)]
        median_price = price_median(x.price for x in comparable)
        all_tags = sorted({tag_value for offer in group for tag_value in (offer.tags or [])})
        cards.append(ProductCard(
            slug=product.slug,
            platform=product.platform,
            brand=product.platform,
            display_name=product.display_name,
            subtitle=product.subtitle,
            product_type=product.product_type,
            price_currency=PRICE_CURRENCY,
            lowest_price=min((x.price for x in trusted), default=None),
            related_lowest_price=min((x.price for x in price_scope), default=None),
            offer_count=len(group),
            in_stock_count=len(in_stock),
            comparable_offer_count=sum(1 for x in group if x.is_comparable),
            trusted_offer_count=len(trusted),
            median_price=median_price,
            source_count=len({x.shop_id for x in group}),
            data_quality_score=_data_quality(group, trusted, comparable)[0],
            data_quality_label=_data_quality(group, trusted, comparable)[1],
            official_reference=asdict(reference) if (reference := official_reference_for(product.slug)) else None,
            last_updated_at=max((x.observed_at for x in group), default=None),
            tags=all_tags[:8],
        ))

    if sort == "quality":
        cards.sort(key=lambda x: (x.data_quality_score, x.trusted_offer_count, x.source_count, -(x.lowest_price or Decimal("999999"))), reverse=True)
    elif sort == "updated":
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
    offers = list(db.scalars(_apply_offer_filters(
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .where(Offer.product_id == product.id),
        OfferFilters(source_platform=filters.source_platform),
    )).unique())
    in_stock = [x for x in offers if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
    price_scope = [x for x in in_stock if x.currency == PRICE_CURRENCY]
    comparable_in_stock = [x for x in price_scope if x.is_comparable]
    medians = _median_prices(comparable_in_stock, comparable_only=True)
    trusted_in_stock = [x for x in comparable_in_stock if _is_trusted_offer(x, medians)]
    median_price = price_median(x.price for x in comparable_in_stock)

    all_tags = sorted({tag for offer in offers for tag in (offer.tags or [])})

    breakdown: list[DeliveryPriceSummary] = []
    delivery_groups: dict[str, list[Offer]] = defaultdict(list)
    for offer in offers:
        delivery_groups[offer.delivery_type or "unknown"].append(offer)
    for delivery_type, group in delivery_groups.items():
        group_stock = [x for x in group if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
        group_comparable = [x for x in group_stock if x.currency == PRICE_CURRENCY and x.is_comparable]
        group_median = price_median(x.price for x in group_comparable)
        group_trusted = [x for x in group_comparable if is_trusted_price(x.price, group_median)]
        breakdown.append(DeliveryPriceSummary(
            delivery_type=delivery_type,
            price_currency=PRICE_CURRENCY,
            lowest_price=min((x.price for x in group_trusted), default=None),
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
        brand=product.platform,
        display_name=product.display_name,
        subtitle=product.subtitle,
        description=product.description,
        product_type=product.product_type,
        price_currency=PRICE_CURRENCY,
        lowest_price=min((x.price for x in trusted_in_stock), default=None),
        related_lowest_price=min((x.price for x in price_scope), default=None),
        highest_price=max((x.price for x in trusted_in_stock), default=None),
        offer_count=len(offers),
        in_stock_count=len(in_stock),
        comparable_offer_count=sum(1 for x in offers if x.is_comparable),
        trusted_offer_count=len(trusted_in_stock),
        median_price=median_price,
        source_count=len({x.shop_id for x in offers}),
        data_quality_score=_data_quality(offers, trusted_in_stock, comparable_in_stock)[0],
        data_quality_label=_data_quality(offers, trusted_in_stock, comparable_in_stock)[1],
        official_reference=asdict(reference) if (reference := official_reference_for(product.slug)) else None,
        offer_group_count=group_count,
        last_updated_at=max((x.observed_at for x in offers), default=None),
        tags=all_tags,
        price_breakdown=breakdown,
        snapshot_id=snapshot.id if snapshot else None,
        snapshot_at=snapshot.published_at if snapshot else None,
        offer_groups=offer_groups,
        history=[],
        trend=[],
    )


def _product_trend(
    db: Session,
    product_id: int,
    *,
    source_platform: str = "",
) -> list[PriceTrendPoint]:
    return _price_trend(db, product_id, currency=PRICE_CURRENCY, source_platform=source_platform)


def get_product_history(
    db: Session,
    slug: str,
    *,
    source_platform: str = "",
) -> ProductHistoryResponse | None:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product is None:
        return None
    trend = _product_trend(db, product.id, source_platform=source_platform)
    return ProductHistoryResponse(trend=trend)


def get_product_offer_page(
    db: Session,
    slug: str,
    *,
    offset: int,
    limit: int,
    filters: OfferFilters = OfferFilters(),
    snapshot_id: int | None = None,
) -> list[OfferPublic] | None:
    product_id = db.scalar(select(Product.id).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product_id is None:
        return None
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, snapshot=snapshot)
        .where(Offer.product_id == product_id),
        filters,
    )
    stmt = (
        stmt
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
    currency: str = "",
    filters: OfferFilters = OfferFilters(),
    snapshot_id: int | None = None,
) -> list[OfferPublic] | None:
    product_id = db.scalar(select(Product.id).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product_id is None:
        return None
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, snapshot=snapshot)
        .where(
            Offer.product_id == product_id,
            Offer.item_fingerprint == fingerprint,
        ),
        filters,
    )
    if currency:
        stmt = stmt.where(Offer.currency == currency.upper())
    offers = list(db.scalars(stmt.order_by(*_offer_ordering())).unique())
    medians = _median_prices(offers, comparable_only=True)
    return [_offer_public(offer, median_price=medians.get(_median_key(offer))) for offer in offers]


def get_offer_description(db: Session, offer_id: int) -> str | None:
    offer = db.scalar(_base_public_offer_query(db).where(Offer.id == offer_id))
    if offer is None:
        return None
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    return _plain_text(raw_json.get("description"))


def get_shop_detail(db: Session, token: str) -> ShopDetail | None:
    disabled_platforms = get_disabled_source_platforms()
    shop_conditions = [Shop.token == token, Shop.is_visible.is_(True)]
    if disabled_platforms:
        shop_conditions.append(Shop.platform.notin_(disabled_platforms))
    shop = db.scalar(select(Shop).where(*shop_conditions))
    if shop is None:
        return None
    snapshot = get_current_snapshot(db)
    offers = list(db.scalars(
        _base_public_offer_query(db, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.shop_id == shop.id, Product.is_visible.is_(True))
        .order_by(*_offer_ordering())
    ).unique())
    medians = _median_prices(offers, comparable_only=True)
    product_conditions = [
        Offer.shop_id == shop.id,
        Offer.active.is_(True),
        Offer.approved.is_(True),
        Offer.product_id.is_not(None),
        Product.is_visible.is_(True),
        Offer.observed_at >= _fresh_cutoff(),
    ]
    if disabled_platforms:
        product_conditions.append(Shop.platform.notin_(disabled_platforms))
    product_stmt = (
        select(
            Product.slug,
            Product.display_name,
            func.count(Offer.id).label("offer_count"),
            func.sum(
                case((or_(Offer.stock_count > 0, Offer.stock_status == "in_stock"), 1), else_=0)
            ).label("in_stock_count"),
        )
        .join(Offer, Offer.product_id == Product.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(*product_conditions)
        .group_by(Product.id)
        .order_by(Product.display_name.asc(), Product.slug.asc())
    )
    if snapshot is not None:
        product_stmt = product_stmt.where(Offer.snapshot_id == snapshot.id)
    products = [
        ShopProduct(
            slug=slug,
            display_name=display_name,
            offer_count=offer_count or 0,
            in_stock_count=int(in_stock_count or 0),
        )
        for slug, display_name, offer_count, in_stock_count in db.execute(product_stmt)
    ]
    return ShopDetail(
        token=shop.token,
        name=shop.name or shop.token,
        source_url=shop.source_url,
        platform=shop.platform,
        source_platform=shop.platform,
        source_platform_label=source_platform_label(shop.platform),
        source_kind=source_kind(shop.platform),
        source_kind_label=source_kind_label(source_kind(shop.platform)),
        status=shop.status,
        first_seen_at=shop.first_seen_at,
        last_success_at=shop.last_success_at,
        last_seen_at=shop.last_seen_at,
        consecutive_failures=shop.consecutive_failures,
        source_health=asdict(source_health(shop)),
        offer_count=len(offers),
        products=products,
        offers=[_offer_public(x, median_price=medians.get(_median_key(x))) for x in offers],
    )


def list_public_shop_tokens(db: Session) -> list[str]:
    """Return shop tokens that have at least one currently public offer."""
    snapshot = get_current_snapshot(db)
    disabled_platforms = get_disabled_source_platforms()
    conditions = [
        Shop.is_visible.is_(True),
        Product.is_visible.is_(True),
        Offer.active.is_(True),
        Offer.approved.is_(True),
        Offer.observed_at >= _fresh_cutoff(),
    ]
    if disabled_platforms:
        conditions.append(Shop.platform.notin_(disabled_platforms))
    stmt = (
        select(Shop.token)
        .join(Offer, Offer.shop_id == Shop.id)
        .join(Product, Offer.product_id == Product.id)
        .where(*conditions)
        .distinct()
        .order_by(Shop.token.asc())
    )
    if snapshot is not None:
        stmt = stmt.where(Offer.snapshot_id == snapshot.id)
    return list(db.scalars(stmt))


def list_public_shops(
    db: Session,
    *,
    source_platform: str = "",
    q: str = "",
    offset: int = 0,
    limit: int = 50,
    sort: str = "offer_count",
) -> "ShopListResponse":
    """Return paginated ShopCard summaries for shops with public offers.

    Only shops that are visible and have at least one currently active,
    approved, non-stale offer linked to a visible product are included.
    """
    from sqlalchemy import func as sqlfunc

    from ..schemas import ShopCard, ShopListResponse
    from .source_platform import canonical_source_platform

    snapshot = get_current_snapshot(db)
    cutoff = _fresh_cutoff()
    platform_filter = canonical_source_platform(source_platform) if source_platform else ""
    disabled_platforms = get_disabled_source_platforms()

    conditions = [
        Shop.is_visible.is_(True),
        Product.is_visible.is_(True),
        Offer.active.is_(True),
        Offer.approved.is_(True),
        Offer.observed_at >= cutoff,
    ]
    if disabled_platforms:
        conditions.append(Shop.platform.notin_(disabled_platforms))

    base = (
        select(
            Shop,
            sqlfunc.count(Offer.id.distinct()).label("offer_count"),
            sqlfunc.sum(
                case((or_(Offer.stock_count > 0, Offer.stock_status == "in_stock"), 1), else_=0)
            ).label("in_stock_count"),
            sqlfunc.count(Offer.product_id.distinct()).label("product_count"),
        )
        .join(Offer, Offer.shop_id == Shop.id)
        .join(Product, Offer.product_id == Product.id)
        .where(*conditions)
        .group_by(Shop.id)
    )

    if snapshot is not None:
        base = base.where(Offer.snapshot_id == snapshot.id)

    if platform_filter:
        base = base.where(Shop.platform == platform_filter)

    if q:
        base = base.where(Shop.name.ilike(f"%{q}%"))

    # Count total before pagination
    count_stmt = select(sqlfunc.count()).select_from(base.subquery())
    total: int = db.scalar(count_stmt) or 0

    # Sorting
    offer_count = sqlfunc.count(Offer.id.distinct())
    sort_columns = {
        "offer_count": [offer_count.desc(), Shop.name.asc().nulls_last(), Shop.token.asc()],
        "name": [Shop.name.asc().nulls_last(), Shop.token.asc()],
        "last_seen": [Shop.last_seen_at.desc().nulls_last(), Shop.token.asc()],
    }.get(sort, [offer_count.desc(), Shop.name.asc().nulls_last(), Shop.token.asc()])
    base = base.order_by(*sort_columns).offset(offset).limit(limit)

    rows = db.execute(base).all()

    # Fetch product slugs per shop (separate query to avoid N+1 on large sets)
    shop_ids = [row.Shop.id for row in rows]
    slugs_by_shop: dict[int, list[str]] = defaultdict(list)
    if shop_ids:
        slug_stmt = (
            select(Offer.shop_id, Product.slug)
            .join(Product, Offer.product_id == Product.id)
            .where(
                Offer.shop_id.in_(shop_ids),
                Offer.active.is_(True),
                Offer.approved.is_(True),
                Offer.observed_at >= cutoff,
                Product.is_visible.is_(True),
            )
            .distinct()
            .order_by(Offer.shop_id.asc(), Product.slug.asc())
        )
        if snapshot is not None:
            slug_stmt = slug_stmt.where(Offer.snapshot_id == snapshot.id)
        for shop_id, slug in db.execute(slug_stmt):
            slugs_by_shop[shop_id].append(slug)

    items = [
        ShopCard(
            token=row.Shop.token,
            name=row.Shop.name,
            source_url=row.Shop.source_url,
            source_platform=canonical_source_platform(row.Shop.platform),
            source_platform_label=source_platform_label(row.Shop.platform),
            offer_count=row.offer_count or 0,
            in_stock_count=int(row.in_stock_count or 0),
            product_count=row.product_count or 0,
            first_seen_at=row.Shop.first_seen_at,
            last_seen_at=row.Shop.last_seen_at,
            last_success_at=row.Shop.last_success_at,
            product_slugs=slugs_by_shop.get(row.Shop.id, []),
        )
        for row in rows
    ]
    return ShopListResponse(items=items, total=total)
