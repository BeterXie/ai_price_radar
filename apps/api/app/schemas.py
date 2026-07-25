from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OfferPublic(BaseModel):
    id: int
    shop_token: str
    shop_name: str
    original_name: str
    original_category: str
    original_description: str
    goods_type: str
    price: Decimal | None
    market_price: Decimal | None
    currency: str
    stock_count: int | None
    stock_status: str
    auto_delivery: bool | None
    tags: list[str]
    risk_flags: list[str]
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    observed_at: datetime


class ProductCard(BaseModel):
    slug: str
    platform: str
    display_name: str
    subtitle: str
    product_type: str
    lowest_price: Decimal | None
    offer_count: int
    in_stock_count: int
    last_updated_at: datetime | None
    tags: list[str]


class PricePoint(BaseModel):
    observed_at: datetime
    price: Decimal | None
    stock_status: str


class ProductDetail(ProductCard):
    description: str
    offers: list[OfferPublic]
    history: list[PricePoint]


class OfferPageResponse(BaseModel):
    items: list[OfferPublic]


class ShopDetail(BaseModel):
    token: str
    name: str
    source_url: str
    platform: str
    status: str
    first_seen_at: datetime
    last_success_at: datetime | None
    offer_count: int
    offers: list[OfferPublic]


class CatalogResponse(BaseModel):
    items: list[ProductCard]
    total: int


class MetaResponse(BaseModel):
    platforms: list[str]
    product_types: list[str]
    tags: list[str]


class ReportCreate(BaseModel):
    offer_id: int | None = None
    kind: Literal["correction", "unavailable", "fraud_concern", "shop_request", "other"] = "correction"
    message: str = Field(min_length=10, max_length=2000)
    contact: str = Field(default="", max_length=200)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int | None
    kind: str
    message: str
    contact: str
    status: str
    created_at: datetime


class AdminOfferUpdate(BaseModel):
    approved: bool | None = None
    active: bool | None = None
    product_slug: str | None = None
    hidden_reason: str | None = Field(default=None, max_length=500)


class AdminReportUpdate(BaseModel):
    status: Literal["open", "reviewing", "resolved", "rejected"]


class AdminStats(BaseModel):
    shops: int
    products: int
    offers: int
    public_offers: int
    open_reports: int
    last_scan_at: datetime | None
