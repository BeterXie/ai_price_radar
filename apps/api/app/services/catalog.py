from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from ..core.config import get_settings
from ..models import Offer, OfferHistory, Product, RawProduct, Shop
from ..schemas import OfferPublic, PricePoint, ProductCard, ProductDetail, ShopDetail


DEFAULT_OFFER_PAGE_SIZE = 30


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


def _offer_public(offer: Offer) -> OfferPublic:
    raw_json = offer.raw_product.raw_json if isinstance(offer.raw_product.raw_json, dict) else {}
    return OfferPublic(
        id=offer.id,
        shop_token=offer.shop.token,
        shop_name=offer.shop.name or offer.shop.token,
        original_name=offer.raw_product.original_name,
        original_category=_plain_text(offer.raw_product.original_category, 300),
        original_description=_plain_text(raw_json.get("description")),
        goods_type=_plain_text(raw_json.get("goods_type"), 120),
        price=offer.price,
        market_price=_raw_decimal(raw_json.get("market_price")),
        currency=offer.currency,
        stock_count=offer.stock_count,
        stock_status=offer.stock_status,
        auto_delivery=offer.auto_delivery,
        tags=offer.tags or [],
        risk_flags=offer.risk_flags or [],
        source_url=offer.source_url,
        first_seen_at=offer.raw_product.first_seen_at,
        last_seen_at=offer.raw_product.last_seen_at,
        observed_at=offer.observed_at,
    )


def _base_public_offer_query(*, include_details: bool = True):
    stmt = (
        select(Offer)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Offer.product_id.is_not(None),
            Shop.is_visible.is_(True),
            Offer.observed_at >= _fresh_cutoff(),
        )
    )
    if include_details:
        stmt = stmt.options(joinedload(Offer.shop), joinedload(Offer.raw_product))
    return stmt


def _offer_ordering():
    return (
        case((Offer.stock_status == "in_stock", 0), else_=1),
        case((Offer.price.is_(None), 1), else_=0),
        Offer.price.asc(),
        Offer.observed_at.desc(),
        Offer.id.asc(),
    )


def _product_offer_page(db: Session, product_id: int, *, offset: int, limit: int) -> list[OfferPublic]:
    stmt = (
        _base_public_offer_query()
        .where(Offer.product_id == product_id)
        .order_by(*_offer_ordering())
        .offset(offset)
        .limit(limit)
    )
    return [_offer_public(offer) for offer in db.scalars(stmt).unique()]


def list_product_cards(
    db: Session,
    *,
    q: str = "",
    platform: str = "",
    product_slug: str = "",
    product_type: str = "",
    tag: str = "",
    in_stock: bool = False,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sort: str = "price",
) -> list[ProductCard]:
    stmt = (_base_public_offer_query(include_details=False)
        .join(Product, Offer.product_id == Product.id)
        .options(contains_eager(Offer.product))
        .join(RawProduct, Offer.raw_product_id == RawProduct.id)
        .where(Product.is_visible.is_(True)))
    if platform:
        stmt = stmt.where(Product.platform == platform)
    if product_slug:
        stmt = stmt.where(Product.slug == product_slug)
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Product.display_name.ilike(pattern), Product.slug.ilike(pattern), RawProduct.original_name.ilike(pattern)))
    if in_stock:
        stmt = stmt.where(Offer.stock_status == "in_stock")
    if min_price is not None:
        stmt = stmt.where(Offer.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Offer.price <= max_price)

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
        in_stock_offers = [x for x in group if x.stock_status == "in_stock" and x.price is not None and x.price > 0]
        lowest = min((x.price for x in in_stock_offers), default=None)
        all_tags = sorted({t for x in group for t in (x.tags or [])})
        cards.append(ProductCard(
            slug=product.slug,
            platform=product.platform,
            display_name=product.display_name,
            subtitle=product.subtitle,
            product_type=product.product_type,
            lowest_price=lowest,
            offer_count=len(group),
            in_stock_count=len(in_stock_offers),
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


def get_product_detail(db: Session, slug: str) -> ProductDetail | None:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product is None:
        return None
    stmt = _base_public_offer_query(include_details=False).where(Offer.product_id == product.id)
    offers = list(db.scalars(stmt).unique())
    in_stock_offers = [x for x in offers if x.stock_status == "in_stock" and x.price is not None and x.price > 0]

    history_stmt = (
        select(OfferHistory)
        .join(Offer, OfferHistory.offer_id == Offer.id)
        .where(Offer.product_id == product.id)
        .order_by(OfferHistory.observed_at.desc())
        .limit(120)
    )
    history = list(db.scalars(history_stmt))
    history.reverse()
    all_tags = sorted({t for x in offers for t in (x.tags or [])})
    return ProductDetail(
        slug=product.slug,
        platform=product.platform,
        display_name=product.display_name,
        subtitle=product.subtitle,
        description=product.description,
        product_type=product.product_type,
        lowest_price=min((x.price for x in in_stock_offers), default=None),
        offer_count=len(offers),
        in_stock_count=len(in_stock_offers),
        last_updated_at=max((x.observed_at for x in offers), default=None),
        tags=all_tags,
        offers=_product_offer_page(db, product.id, offset=0, limit=DEFAULT_OFFER_PAGE_SIZE),
        history=[PricePoint(observed_at=x.observed_at, price=x.price, stock_status=x.stock_status) for x in history],
    )


def get_product_offer_page(db: Session, slug: str, *, offset: int, limit: int) -> list[OfferPublic] | None:
    product_id = db.scalar(select(Product.id).where(Product.slug == slug, Product.is_visible.is_(True)))
    if product_id is None:
        return None
    return _product_offer_page(db, product_id, offset=offset, limit=limit)


def get_shop_detail(db: Session, token: str) -> ShopDetail | None:
    shop = db.scalar(select(Shop).where(Shop.token == token, Shop.is_visible.is_(True)))
    if shop is None:
        return None
    offers = list(db.scalars(
        _base_public_offer_query()
        .join(Product, Offer.product_id == Product.id)
        .where(Offer.shop_id == shop.id, Product.is_visible.is_(True))
    ).unique())
    offers.sort(key=lambda x: (x.stock_status != "in_stock", x.price is None, x.price or Decimal("999999")))
    return ShopDetail(
        token=shop.token,
        name=shop.name or shop.token,
        source_url=shop.source_url,
        platform=shop.platform,
        status=shop.status,
        first_seen_at=shop.first_seen_at,
        last_success_at=shop.last_success_at,
        offer_count=len(offers),
        offers=[_offer_public(x) for x in offers],
    )
