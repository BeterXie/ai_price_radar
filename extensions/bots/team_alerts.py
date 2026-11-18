"""OpenAI Team offers at or below CNY 20 in a published snapshot."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import CatalogSnapshot, Offer, Product, Shop
from app.services.account_plans import account_plan
from app.services.catalog import _base_public_offer_query, _fresh_cutoff


TEAM_PRICE_LIMIT = Decimal("20.00")


@dataclass(frozen=True, slots=True)
class TeamLowPriceOffer:
    offer_id: int
    product_name: str
    shop_name: str
    price: Decimal
    product_url: str


def is_team_account_title(title: str) -> bool:
    text = unicodedata.normalize("NFKC", title).casefold().replace("×", "x").replace("✖", "x").replace("\ufe0f", "")
    # A free/base account advertised as usable for opening Team is not a Team
    # subscription. Other vendors also sell products called "Team 5x".
    if account_plan("chatgpt", text, "") == "chatgpt-account" or re.search(
        r"claude|anthropic|cursor|gemini|(?<![a-z])free(?![a-z])|未开通|待开通|可开通|基础账号|无订阅|教程",
        text,
    ):
        return False
    has_team = bool(
        re.search(r"(?<![a-z])team(?![a-z])|(?<![a-z0-9])(?:5|10)\s*x\s*team(?![a-z])", text)
    )
    has_team_multiplier = bool(re.search(r"(?<!\d)(?:5|10)\s*(?:倍|x(?=team|[^a-z0-9]|$))", text))
    if has_team and has_team_multiplier:
        return True
    return bool(
        re.search(r"(?<![a-z])team(?![a-z])", text)
        and re.search(r"(?<![一二三四五六七八九十百零\d])(?:二|2)\s*车", text)
    )


def collect_team_low_price_offers(db: Session, snapshot: CatalogSnapshot) -> list[TeamLowPriceOffer]:
    if snapshot.published_at is None:
        return []
    stmt = (
        _base_public_offer_query(
            db,
            snapshot=snapshot,
            cutoff=_fresh_cutoff(),
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
            Offer.price <= TEAM_PRICE_LIMIT,
        )
        .order_by(Offer.price, Offer.id)
    )
    return [
        TeamLowPriceOffer(
            offer_id=offer.id,
            product_name=offer.raw_product.original_name,
            shop_name=offer.shop.name,
            price=offer.price,
            product_url=offer.source_url or offer.raw_product.source_url,
        )
        for offer in db.scalars(stmt)
        if is_team_account_title(offer.raw_product.original_name)
    ]
