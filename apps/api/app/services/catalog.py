from __future__ import annotations

import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from statistics import median
from typing import Any

from sqlalchemy import Float, Text, and_, case, cast, false, func, literal, not_, or_, select
from sqlalchemy.orm import Session, contains_eager

from ..core.config import get_settings
from ..models import CatalogSnapshot, Offer, OfferClick, OfferHistory, Product, RawProduct, Shop
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
    public_https_url_or_empty,
    source_kind,
    source_kind_label,
    source_platform_label,
)


DEFAULT_OFFER_PAGE_SIZE = 30
PRICE_CURRENCY = "CNY"


class SnapshotNotFoundError(LookupError):
    def __init__(self, snapshot_id: int):
        super().__init__(f"published snapshot {snapshot_id} not found")
        self.snapshot_id = snapshot_id


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
    return result if result.is_finite() and result > 0 else None


def _fresh_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=get_settings().stale_offer_hours)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _snapshot_cutoff(db: Session, snapshot: CatalogSnapshot | None) -> datetime:
    """Use a fixed publication-time window for historical snapshots."""
    current = get_current_snapshot(db)
    if (
        snapshot is not None
        and snapshot.published_at is not None
        and (current is None or snapshot.id != current.id)
    ):
        reference = _as_utc(snapshot.published_at)
        return reference - timedelta(hours=get_settings().stale_offer_hours)
    return _fresh_cutoff()


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
        if snapshot is None:
            raise SnapshotNotFoundError(snapshot_id)
        return snapshot
    return get_current_snapshot(db)


def get_snapshot(db: Session, snapshot_id: int | None = None) -> CatalogSnapshot | None:
    return _snapshot_for_query(db, snapshot_id)


def _base_public_offer_query(
    db: Session,
    *,
    include_details: bool = True,
    snapshot: CatalogSnapshot | None = None,
    cutoff: datetime | None = None,
):
    snapshot = snapshot or get_current_snapshot(db)
    disabled_platforms = get_disabled_source_platforms()
    conditions = [
        Offer.active.is_(True),
        Offer.approved.is_(True),
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
        Offer.product_id.is_not(None),
        Shop.is_visible.is_(True),
        Offer.observed_at >= (cutoff or _snapshot_cutoff(db, snapshot)),
    ]
    if disabled_platforms:
        conditions.append(Shop.platform.notin_(disabled_platforms))
    stmt = (
        select(Offer)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(RawProduct, Offer.raw_product_id == RawProduct.id)
        .where(*conditions)
    )
    stmt = stmt.where(Offer.snapshot_id == snapshot.id if snapshot is not None else false())
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


def _group_offer_ordering():
    return (
        case((Offer.currency == PRICE_CURRENCY, 0), else_=1),
        Offer.currency.asc(),
        case((Offer.price.is_(None), 1), else_=0),
        Offer.price.asc(),
        case((Offer.stock_status == "in_stock", 0), else_=1),
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
        source_url=public_https_url_or_empty(offer.source_url),
        click_count=int(getattr(offer, "click_count", 0) or 0),
        first_seen_at=offer.raw_product.first_seen_at,
        last_seen_at=offer.raw_product.last_seen_at,
        observed_at=offer.observed_at,
    )


def _median_key(offer: Offer) -> tuple[int | None, str, str]:
    return offer.product_id, offer.delivery_type or "unknown", offer.currency or PRICE_CURRENCY


def _median_prices(offers: list[Offer], *, comparable_only: bool = False) -> dict[tuple[int | None, str, str], Decimal]:
    grouped: dict[tuple[int | None, str, str], list[Decimal]] = defaultdict(list)
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


def _is_trusted_offer(offer: Offer, medians: dict[tuple[int | None, str, str], Decimal]) -> bool:
    return (
        offer.stock_status == "in_stock"
        and bool(offer.is_comparable)
        and is_trusted_price(offer.price, medians.get(_median_key(offer)))
    )


def _trusted_offer_sort_key(offer: Offer, medians: dict[tuple[int | None, str, str], Decimal] | None = None):
    return _offer_sort_key(offer)


def _group_offers(
    offers: list[Offer],
    medians: dict[tuple[int | None, str, str], Decimal] | None = None,
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


class _TrendCache:
    """Thread-safe TTL + LRU cache for per-product price trend aggregation."""

    def __init__(self, *, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._entries: OrderedDict[tuple, tuple[float, list[PriceTrendPoint]]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple, *, ttl_seconds: float) -> list[PriceTrendPoint] | None:
        if ttl_seconds <= 0:
            return None
        moment = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if moment - stored_at > ttl_seconds:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def put(self, key: tuple, value: list[PriceTrendPoint]) -> None:
        moment = time.monotonic()
        with self._lock:
            self._entries[key] = (moment, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_trend_cache = _TrendCache()


def clear_price_trend_cache() -> None:
    """Reset the in-process price trend cache (tests and admin tooling)."""
    _trend_cache.clear()


def _day_bucket_column(dialect_name: str):
    """UTC calendar-day bucketing expression usable in GROUP BY on both dialects."""
    if dialect_name == "postgresql":
        # timezone('UTC', timestamptz) renders the timestamp in UTC; date_trunc
        # then yields the UTC calendar day regardless of the session timezone.
        return func.date_trunc("day", func.timezone("UTC", OfferHistory.observed_at))
    # SQLite stores datetimes as UTC ISO text, so the date prefix is the UTC day.
    return func.substr(cast(OfferHistory.observed_at, Text), 1, 10)


def _bucket_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _weighted_median(pairs: list[tuple[Decimal, int]]) -> Decimal | None:
    """Median of a multiset given as (price, count) pairs, mirroring statistics.median."""
    ordered = sorted((price, count) for price, count in pairs if count > 0)
    total = sum(count for _, count in ordered)
    if total == 0:
        return None

    def value_at(position: int) -> Decimal:
        running = 0
        for price, count in ordered:
            running += count
            if position < running:
                return price
        return ordered[-1][0]

    if total % 2:
        return value_at(total // 2)
    return (value_at(total // 2 - 1) + value_at(total // 2)) / Decimal(2)


def _price_trend(
    db: Session,
    product_id: int,
    *,
    currency: str = PRICE_CURRENCY,
    source_platform: str = "",
    day_limit: int = 90,
) -> list[PriceTrendPoint]:
    """Daily price trend computed with database-side aggregation.

    offer_history grows without bound, so materializing one ORM object pair
    per record (the previous implementation) exhausted the API container's
    memory on busy days. The trend now collapses to one count row per day and
    one row per (day, delivery, price) group inside the database; the Python
    side only reconstructs medians from that bounded histogram. Results are
    cached per product and invalidated when the current snapshot changes.
    """
    snapshot = get_current_snapshot(db)
    ttl_seconds = float(get_settings().price_trend_cache_ttl_seconds)
    cache_key = (
        product_id,
        currency,
        source_platform,
        day_limit,
        snapshot.id if snapshot is not None else None,
    )
    cached = _trend_cache.get(cache_key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return cached

    cutoff = datetime.now(timezone.utc) - timedelta(days=day_limit)
    conditions: list[Any] = [
        Offer.product_id == product_id,
        Offer.approved.is_(True),
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
        Shop.is_visible.is_(True),
        CatalogSnapshot.published_at.is_not(None),
        OfferHistory.currency == currency,
        OfferHistory.observed_at >= cutoff,
    ]
    if source_platform:
        conditions.append(Shop.platform == source_platform)
    disabled_platforms = get_disabled_source_platforms()
    if disabled_platforms:
        conditions.append(Shop.platform.notin_(disabled_platforms))

    bucket = _day_bucket_column(db.get_bind().dialect.name)

    count_rows = db.execute(
        select(
            bucket.label("bucket"),
            func.count().label("observation_count"),
            func.sum(case((OfferHistory.stock_status == "in_stock", 1), else_=0)).label("in_stock_count"),
        )
        .join(Offer, OfferHistory.offer_id == Offer.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(CatalogSnapshot, Offer.snapshot_id == CatalogSnapshot.id)
        .where(*conditions)
        .group_by(bucket)
    ).all()

    delivery_column = func.coalesce(func.nullif(Offer.delivery_type, ""), "unknown")
    histogram_rows = db.execute(
        select(
            bucket.label("bucket"),
            delivery_column.label("delivery_type"),
            OfferHistory.price.label("price"),
            func.count().label("price_count"),
        )
        .join(Offer, OfferHistory.offer_id == Offer.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .join(CatalogSnapshot, Offer.snapshot_id == CatalogSnapshot.id)
        .where(
            *conditions,
            Offer.is_comparable.is_(True),
            OfferHistory.stock_status == "in_stock",
            OfferHistory.price.is_not(None),
            OfferHistory.price > 0,
        )
        .group_by(bucket, delivery_column, OfferHistory.price)
    ).all()

    counts = {
        _bucket_datetime(row.bucket): (int(row.observation_count), int(row.in_stock_count or 0))
        for row in count_rows
    }
    histogram: dict[datetime, dict[str, list[tuple[Decimal, int]]]] = defaultdict(lambda: defaultdict(list))
    for row in histogram_rows:
        histogram[_bucket_datetime(row.bucket)][row.delivery_type].append((row.price, int(row.price_count)))

    result: list[PriceTrendPoint] = []
    for day in sorted(counts):
        observation_count, in_stock_count = counts[day]
        delivery_prices = histogram.get(day, {})
        delivery_medians = {
            delivery: _weighted_median(pairs)
            for delivery, pairs in delivery_prices.items()
        }
        trusted_lowest: Decimal | None = None
        for delivery, pairs in delivery_prices.items():
            delivery_median = delivery_medians[delivery]
            for price, _count in pairs:
                if is_trusted_price(price, delivery_median) and (trusted_lowest is None or price < trusted_lowest):
                    trusted_lowest = price
        median_price = _weighted_median(
            [pair for pairs in delivery_prices.values() for pair in pairs]
        )
        result.append(PriceTrendPoint(
            bucket_at=day,
            price_currency=currency,
            trusted_lowest_price=trusted_lowest,
            median_price=median_price,
            in_stock_count=in_stock_count,
            observation_count=observation_count,
        ))

    _trend_cache.put(cache_key, result)
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
    cutoff = _snapshot_cutoff(db, snapshot)
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, include_details=False, snapshot=snapshot, cutoff=cutoff)
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
        detail_stmt = _base_public_offer_query(db, snapshot=snapshot, cutoff=cutoff).where(Offer.id.in_(representative_ids))
        representatives = {offer.id: offer for offer in db.scalars(detail_stmt).unique()}
    medians = _median_prices(offers, comparable_only=True)

    items: list[OfferGroupPublic] = []
    for fingerprint, group in selected:
        representative = representatives.get(group[0].id)
        if representative is None:
            continue
        in_stock = [offer for offer in group if offer.stock_status == "in_stock"]
        in_stock_prices = [
            offer.price
            for offer in in_stock
            if offer.currency == PRICE_CURRENCY and offer.price is not None and offer.price >= MIN_TRUSTED_PRICE
        ] or [
            offer.price
            for offer in in_stock
            if offer.currency == PRICE_CURRENCY and offer.price is not None
        ]
        all_prices = [
            offer.price
            for offer in group
            if offer.currency == PRICE_CURRENCY and offer.price is not None and offer.price >= MIN_TRUSTED_PRICE
        ] or [
            offer.price
            for offer in group
            if offer.currency == PRICE_CURRENCY and offer.price is not None
        ]
        prices = in_stock_prices or all_prices
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
            click_count=sum(int(getattr(offer, "click_count", 0) or 0) for offer in group),
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
    cutoff = _snapshot_cutoff(db, snapshot)
    stmt = (
        _base_public_offer_query(db, include_details=False, snapshot=snapshot, cutoff=cutoff)
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
    filtered_stmt = _apply_offer_filters(stmt, filters)
    fingerprint = func.coalesce(
        func.nullif(Offer.item_fingerprint, ""),
        literal("offer-") + cast(Offer.id, Text),
    )
    stock_rank = case((Offer.stock_status == "in_stock", 0), else_=1)
    comparable_rank = case((Offer.is_comparable.is_(True), 0), else_=1)
    currency_rank = case((Offer.currency == PRICE_CURRENCY, 0), else_=1)
    price_missing_rank = case((Offer.price.is_(None), 1), else_=0)
    low_price_rank = case(
        (and_(Offer.price.is_not(None), Offer.price < MIN_TRUSTED_PRICE), 1),
        else_=0,
    )
    representative_order = (
        stock_rank,
        comparable_rank,
        currency_rank,
        Offer.currency.asc(),
        price_missing_rank,
        low_price_rank,
        Offer.price.asc(),
        Offer.observed_at.desc(),
        Offer.id.asc(),
    )
    ranked = filtered_stmt.with_only_columns(
        Offer.id.label("offer_id"),
        Offer.product_id.label("product_id"),
        fingerprint.label("fingerprint"),
        Offer.shop_id.label("shop_id"),
        Offer.stock_status.label("stock_status"),
        Offer.currency.label("currency"),
        Offer.price.label("price"),
        Offer.click_count.label("click_count"),
        Offer.observed_at.label("observed_at"),
        Offer.is_comparable.label("is_comparable"),
        func.coalesce(Offer.delivery_type, "unknown").label("delivery_type"),
        stock_rank.label("stock_rank"),
        comparable_rank.label("comparable_rank"),
        currency_rank.label("currency_rank"),
        price_missing_rank.label("price_missing_rank"),
        low_price_rank.label("low_price_rank"),
        func.row_number().over(
            partition_by=(Offer.product_id, fingerprint),
            order_by=representative_order,
        ).label("representative_rank"),
        maintain_column_froms=True,
    ).subquery()

    representative_value = lambda column: func.max(
        case((ranked.c.representative_rank == 1, column), else_=None)
    )
    in_stock = ranked.c.stock_status == "in_stock"
    cny_price = and_(ranked.c.currency == PRICE_CURRENCY, ranked.c.price.is_not(None))
    in_stock_cny = and_(in_stock, cny_price)
    trusted_price = and_(cny_price, ranked.c.price >= MIN_TRUSTED_PRICE)
    in_stock_trusted = and_(in_stock, trusted_price)
    grouped = select(
        ranked.c.product_id,
        ranked.c.fingerprint,
        representative_value(ranked.c.offer_id).label("representative_id"),
        representative_value(ranked.c.stock_rank).label("representative_stock_rank"),
        representative_value(ranked.c.comparable_rank).label("representative_comparable_rank"),
        representative_value(ranked.c.currency_rank).label("representative_currency_rank"),
        representative_value(ranked.c.currency).label("representative_currency"),
        representative_value(ranked.c.price_missing_rank).label("representative_price_missing_rank"),
        representative_value(ranked.c.low_price_rank).label("representative_low_price_rank"),
        representative_value(ranked.c.price).label("representative_price"),
        representative_value(ranked.c.observed_at).label("representative_observed_at"),
        func.count().label("offer_count"),
        func.count(func.distinct(ranked.c.shop_id)).label("shop_count"),
        func.sum(case((in_stock, 1), else_=0)).label("in_stock_count"),
        func.coalesce(
            func.min(case((in_stock_trusted, ranked.c.price), else_=None)),
            func.min(case((in_stock_cny, ranked.c.price), else_=None)),
            func.min(case((trusted_price, ranked.c.price), else_=None)),
            func.min(case((cny_price, ranked.c.price), else_=None)),
        ).label("lowest_price"),
        func.coalesce(
            func.max(case((in_stock_trusted, ranked.c.price), else_=None)),
            func.max(case((in_stock_cny, ranked.c.price), else_=None)),
            func.max(case((trusted_price, ranked.c.price), else_=None)),
            func.max(case((cny_price, ranked.c.price), else_=None)),
        ).label("highest_price"),
        func.sum(func.coalesce(ranked.c.click_count, 0)).label("click_count"),
        func.max(ranked.c.observed_at).label("latest_observed_at"),
    ).group_by(ranked.c.product_id, ranked.c.fingerprint).subquery()

    total_groups = int(db.scalar(select(func.count()).select_from(grouped)) or 0)
    selected = list(db.execute(
        select(grouped)
        .order_by(
            grouped.c.representative_stock_rank,
            grouped.c.representative_comparable_rank,
            grouped.c.representative_currency_rank,
            grouped.c.representative_currency,
            grouped.c.representative_price_missing_rank,
            grouped.c.representative_low_price_rank,
            grouped.c.representative_price,
            grouped.c.representative_observed_at.desc(),
            grouped.c.representative_id,
        )
        .offset(offset)
        .limit(limit)
    ).mappings())

    representative_ids = [int(row["representative_id"]) for row in selected]
    representatives: dict[int, Offer] = {}
    if representative_ids:
        detail_stmt = _base_public_offer_query(db, snapshot=snapshot, cutoff=cutoff).where(Offer.id.in_(representative_ids))
        representatives = {offer.id: offer for offer in db.scalars(detail_stmt).unique()}
    product_ids = {int(row["product_id"]) for row in selected}
    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids)))
    } if product_ids else {}
    median_values: dict[tuple[int, str, str], list[Decimal]] = defaultdict(list)
    for row in db.execute(
        select(
            ranked.c.product_id,
            ranked.c.delivery_type,
            ranked.c.currency,
            ranked.c.price,
        ).where(
            ranked.c.stock_status == "in_stock",
            ranked.c.is_comparable.is_(True),
            ranked.c.price.is_not(None),
            ranked.c.price > 0,
        )
    ):
        median_values[(int(row.product_id), row.delivery_type, row.currency)].append(row.price)
    medians = {
        key: median_price
        for key, prices in median_values.items()
        if (median_price := price_median(prices)) is not None
    }
    metrics = db.execute(
        select(
            func.count().label("offer_total"),
            func.sum(case((ranked.c.stock_status == "in_stock", 1), else_=0)).label("in_stock_count"),
            func.sum(case((ranked.c.is_comparable.is_(True), 1), else_=0)).label("comparable_count"),
            func.max(ranked.c.observed_at).label("last_updated_at"),
        ).select_from(ranked)
    ).one()
    trusted_count = sum(
        1
        for key, prices in median_values.items()
        if key[2] == PRICE_CURRENCY
        for price in prices
        if is_trusted_price(price, medians.get(key))
    )

    items: list[OfferGroupPublic] = []
    for row in selected:
        product_id = int(row["product_id"])
        product = products.get(product_id)
        representative = representatives.get(int(row["representative_id"]))
        if product is None or representative is None:
            continue
        items.append(OfferGroupPublic(
            product_slug=product.slug,
            product_name=product.display_name,
            fingerprint=str(row["fingerprint"]),
            representative=_offer_public(
                representative,
                median_price=medians.get(_median_key(representative)),
            ),
            offer_count=int(row["offer_count"] or 0),
            shop_count=int(row["shop_count"] or 0),
            in_stock_count=int(row["in_stock_count"] or 0),
            price_currency=PRICE_CURRENCY,
            lowest_price=row["lowest_price"],
            highest_price=row["highest_price"],
            click_count=int(row["click_count"] or 0),
            latest_observed_at=row["latest_observed_at"],
        ))

    return (
        items,
        total_groups,
        int(metrics.offer_total or 0),
        int(metrics.in_stock_count or 0),
        int(metrics.comparable_count or 0),
        trusted_count,
        metrics.last_updated_at,
    )


def _product_card_scope(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_slugs: tuple[str, ...] = (),
    product_type: str = "",
    tag: str = "",
    filters: OfferFilters = OfferFilters(),
    snapshot_id: int | None = None,
) -> tuple[CatalogSnapshot | None, object]:
    snapshot = _snapshot_for_query(db, snapshot_id)
    stmt = (
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .where(Product.is_visible.is_(True))
    )
    stmt = _apply_offer_filters(stmt, filters)
    if platform:
        stmt = stmt.where(Product.platform == platform)
    if product_slug:
        stmt = stmt.where(Product.slug == product_slug)
    if product_slugs:
        stmt = stmt.where(Product.slug.in_(product_slugs))
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(
            Product.display_name.ilike(pattern),
            Product.slug.ilike(pattern),
            RawProduct.original_name.ilike(pattern),
        ))
    if tag:
        escaped = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(cast(Offer.tags, Text).like(f'%"{escaped}"%', escape="\\"))
    return snapshot, stmt


def _has_offer_filters(filters: OfferFilters) -> bool:
    return any([
        filters.source_platform,
        filters.delivery_type,
        filters.service_period,
        filters.warranty,
        filters.auto_delivery is not None,
        filters.updated_within_hours is not None,
        filters.comparable is not None,
        filters.exclude,
        filters.in_stock,
        filters.min_price is not None,
        filters.max_price is not None,
    ])


def count_product_cards(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_slugs: tuple[str, ...] = (),
    product_type: str = "",
    tag: str = "",
    filters: OfferFilters = OfferFilters(),
    snapshot_id: int | None = None,
) -> int:
    if (product_slug or product_slugs) and not _has_offer_filters(filters) and not q and not tag:
        product_stmt = select(func.count(Product.id)).where(Product.is_visible.is_(True))
        if platform:
            product_stmt = product_stmt.where(Product.platform == platform)
        if product_slug:
            product_stmt = product_stmt.where(Product.slug == product_slug)
        if product_slugs:
            product_stmt = product_stmt.where(Product.slug.in_(product_slugs))
        if product_type:
            product_stmt = product_stmt.where(Product.product_type == product_type)
        return int(db.scalar(product_stmt) or 0)
    _, stmt = _product_card_scope(
        db,
        q=q,
        platform=platform,
        product_slug=product_slug,
        product_slugs=product_slugs,
        product_type=product_type,
        tag=tag,
        filters=filters,
        snapshot_id=snapshot_id,
    )
    product_ids = stmt.with_only_columns(Product.id).distinct().order_by(None).subquery()
    return int(db.scalar(select(func.count()).select_from(product_ids)) or 0)


def _product_card_page_ids(db: Session, stmt, *, sort: str, offset: int, limit: int) -> list[int]:
    in_stock = and_(Offer.stock_status == "in_stock", Offer.price.is_not(None), Offer.price > 0)
    comparable = and_(in_stock, Offer.currency == PRICE_CURRENCY, Offer.is_comparable.is_(True))
    trusted_candidate = and_(comparable, Offer.price >= MIN_TRUSTED_PRICE)
    offer_count = func.count(Offer.id)
    in_stock_count = func.sum(case((in_stock, 1), else_=0))
    comparable_count = func.sum(case((comparable, 1), else_=0))
    trusted_count = func.sum(case((trusted_candidate, 1), else_=0))
    source_count = func.count(func.distinct(Offer.shop_id))
    latest = func.max(Offer.observed_at)
    lowest_price = func.min(case((trusted_candidate, Offer.price), else_=None))
    trusted_ratio = cast(trusted_count, Float) / func.nullif(cast(comparable_count, Float), 0.0)
    source_points = case((source_count >= 5, 25), else_=source_count * 5)
    now = datetime.now(timezone.utc)
    freshness = case(
        (latest >= now - timedelta(hours=6), 30),
        (latest >= now - timedelta(hours=24), 22),
        (latest >= now - timedelta(hours=72), 12),
        else_=0,
    )
    quality_score = func.coalesce(trusted_ratio, 0.0) * 45 + source_points + freshness

    if sort == "updated":
        ordering = (latest.desc(), Product.id.asc())
    elif sort == "offers":
        ordering = (in_stock_count.desc(), offer_count.desc(), Product.id.asc())
    elif sort == "price_desc":
        ordering = (case((lowest_price.is_(None), 1), else_=0), lowest_price.desc(), in_stock_count.desc(), Product.id.asc())
    elif sort == "price":
        ordering = (case((lowest_price.is_(None), 1), else_=0), lowest_price.asc(), in_stock_count.desc(), Product.id.asc())
    else:
        ordering = (
            quality_score.desc(),
            trusted_count.desc(),
            source_count.desc(),
            case((lowest_price.is_(None), 1), else_=0),
            lowest_price.asc(),
            Product.id.asc(),
        )

    page_stmt = (
        stmt.with_only_columns(Product.id.label("product_id"))
        .group_by(Product.id)
        .order_by(*ordering)
        .offset(offset)
        .limit(limit)
    )
    return [int(row.product_id) for row in db.execute(page_stmt)]


def list_product_cards(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_slugs: tuple[str, ...] = (),
    product_type: str = "",
    tag: str = "",
    filters: OfferFilters = OfferFilters(),
    sort: str = "quality",
    snapshot_id: int | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> list[ProductCard]:
    _, stmt = _product_card_scope(
        db,
        q=q,
        platform=platform,
        product_slug=product_slug,
        product_slugs=product_slugs,
        product_type=product_type,
        tag=tag,
        filters=filters,
        snapshot_id=snapshot_id,
    )
    page_ids: list[int] | None = None
    if limit is not None and not (product_slug or product_slugs):
        page_ids = _product_card_page_ids(db, stmt, sort=sort, offset=offset, limit=limit)
        if not page_ids:
            return []
        stmt = stmt.where(Product.id.in_(page_ids))

    offers = list(db.scalars(stmt.options(contains_eager(Offer.product))).unique())
    grouped: dict[int, list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.product_id is None:
            continue
        grouped[offer.product_id].append(offer)

    cards: list[ProductCard] = []
    card_product_ids: dict[str, int] = {}
    for group in grouped.values():
        product = group[0].product
        if product is None:
            continue
        card_product_ids[product.slug] = product.id
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

    existing_product_slugs = {c.slug for c in cards}
    has_offer_filters = _has_offer_filters(filters)
    # Supplement zero-offer product cards only when no query/filter narrows the
    # result set. A tag filter is applied per-offer below, so a product with no
    # matching offers must not reappear here as a zero-offer card.
    if (product_slug or product_slugs) and not has_offer_filters and not q and not tag:
        product_query = select(Product).where(Product.is_visible.is_(True))
        if platform:
            product_query = product_query.where(Product.platform == platform)
        if product_slug:
            product_query = product_query.where(Product.slug == product_slug)
        if product_slugs:
            product_query = product_query.where(Product.slug.in_(product_slugs))
        if product_type:
            product_query = product_query.where(Product.product_type == product_type)
        for prod in db.scalars(product_query):
            if prod.slug not in existing_product_slugs:
                cards.append(ProductCard(
                    slug=prod.slug,
                    platform=prod.platform,
                    brand=prod.platform,
                    display_name=prod.display_name,
                    subtitle=prod.subtitle,
                    product_type=prod.product_type,
                    price_currency=PRICE_CURRENCY,
                    lowest_price=None,
                    related_lowest_price=None,
                    offer_count=0,
                    in_stock_count=0,
                    comparable_offer_count=0,
                    trusted_offer_count=0,
                    median_price=None,
                    source_count=0,
                    data_quality_score=0,
                    data_quality_label="暂无报价",
                    official_reference=asdict(reference) if (reference := official_reference_for(prod.slug)) else None,
                    last_updated_at=None,
                    tags=[],
                ))

    if page_ids is not None:
        page_order = {product_id: index for index, product_id in enumerate(page_ids)}
        cards.sort(key=lambda card: page_order.get(card_product_ids.get(card.slug, -1), len(page_order)))
    elif sort == "quality":
        cards.sort(key=lambda x: (x.data_quality_score, x.trusted_offer_count, x.source_count, -(x.lowest_price or Decimal("999999"))), reverse=True)
    elif sort == "updated":
        cards.sort(key=lambda x: x.last_updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    elif sort == "offers":
        cards.sort(key=lambda x: (x.in_stock_count, x.offer_count), reverse=True)
    elif sort == "price_desc":
        cards.sort(key=lambda x: (x.lowest_price is None, -(x.lowest_price or Decimal("0")), -x.in_stock_count))
    else:
        cards.sort(key=lambda x: (x.lowest_price is None, x.lowest_price or Decimal("999999"), -x.in_stock_count))
    if page_ids is None and limit is not None:
        cards = cards[offset:offset + limit]
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
        filters,
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
    offers = list(db.scalars(stmt.order_by(*_offer_ordering())).unique())
    medians = _median_prices(offers, comparable_only=True)
    return [
        _offer_public(offer, median_price=medians.get(_median_key(offer)))
        for offer in offers[offset:offset + limit]
    ]


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
    fingerprint_condition = Offer.item_fingerprint == fingerprint
    if fingerprint.startswith("offer-") and fingerprint[6:].isdigit():
        fingerprint_condition = or_(
            fingerprint_condition,
            and_(Offer.item_fingerprint == "", Offer.id == int(fingerprint[6:])),
        )
    stmt = _apply_offer_filters(
        _base_public_offer_query(db, snapshot=snapshot)
        .where(
            Offer.product_id == product_id,
            fingerprint_condition,
        ),
        filters,
    )
    if currency:
        stmt = stmt.where(Offer.currency == currency.upper())
    offers = list(db.scalars(stmt.order_by(*_group_offer_ordering())).unique())
    medians = _median_prices(offers, comparable_only=True)
    return [_offer_public(offer, median_price=medians.get(_median_key(offer))) for offer in offers]


def get_offer_description(db: Session, offer_id: int) -> str | None:
    offer = db.scalar(
        _base_public_offer_query(db)
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.id == offer_id, Product.is_visible.is_(True))
    )
    if offer is None:
        return None
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    return _plain_text(raw_json.get("description"))


def get_shop_detail(
    db: Session,
    token: str,
    *,
    offer_offset: int = 0,
    offer_limit: int = DEFAULT_OFFER_PAGE_SIZE,
) -> ShopDetail | None:
    disabled_platforms = get_disabled_source_platforms()
    shop_conditions = [Shop.token == token, Shop.is_visible.is_(True)]
    if disabled_platforms:
        shop_conditions.append(Shop.platform.notin_(disabled_platforms))
    shop = db.scalar(select(Shop).where(*shop_conditions))
    if shop is None:
        return None
    snapshot = get_current_snapshot(db)
    offer_stmt = (
        _base_public_offer_query(db, include_details=False, snapshot=snapshot)
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.shop_id == shop.id, Product.is_visible.is_(True))
    )
    offer_count = int(db.scalar(
        offer_stmt.with_only_columns(func.count(Offer.id)).order_by(None)
    ) or 0)
    offers = list(db.scalars(
        offer_stmt
        .options(contains_eager(Offer.shop), contains_eager(Offer.raw_product))
        .order_by(*_offer_ordering())
        .offset(offer_offset)
        .limit(offer_limit)
    ).unique())
    medians = _median_prices(offers, comparable_only=True)
    product_conditions = [
        Offer.shop_id == shop.id,
        Offer.active.is_(True),
        Offer.approved.is_(True),
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
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
    product_stmt = product_stmt.where(Offer.snapshot_id == snapshot.id if snapshot is not None else false())
    products = [
        ShopProduct(
            slug=slug,
            display_name=display_name,
            offer_count=offer_count or 0,
            in_stock_count=int(in_stock_count or 0),
        )
        for slug, display_name, offer_count, in_stock_count in db.execute(product_stmt)
    ]
    cst = timezone(timedelta(hours=8))
    now_cst = datetime.now(cst)
    today_start_cst = datetime(now_cst.year, now_cst.month, now_cst.day, tzinfo=cst)
    today_start_utc = today_start_cst.astimezone(timezone.utc)

    today_clicks = db.scalar(
        select(func.count(OfferClick.id)).where(
            OfferClick.shop_id == shop.id,
            OfferClick.created_at >= today_start_utc,
        )
    ) or 0

    total_clicks = db.scalar(
        select(func.count(OfferClick.id)).where(
            OfferClick.shop_id == shop.id,
        )
    ) or 0

    return ShopDetail(
        token=shop.token,
        name=shop.name or shop.token,
        source_url=public_https_url_or_empty(shop.source_url),
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
        offer_count=offer_count,
        today_clicks=int(today_clicks),
        total_clicks=int(total_clicks),
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
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
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
    stmt = stmt.where(Offer.snapshot_id == snapshot.id if snapshot is not None else false())
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
        or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
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

    base = base.where(Offer.snapshot_id == snapshot.id if snapshot is not None else false())

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
                or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
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
            source_url=public_https_url_or_empty(row.Shop.source_url),
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
