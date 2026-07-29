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
    original_description: str = ""
    description_available: bool = False
    goods_type: str
    price: Decimal | None
    market_price: Decimal | None
    currency: str
    stock_count: int | None
    stock_status: str
    auto_delivery: bool | None
    tags: list[str]
    risk_flags: list[str]
    delivery_type: str
    is_comparable: bool
    service_period: str
    warranty: str
    use_scenarios: list[str]
    item_fingerprint: str
    low_price_warning: str | None = None
    is_trusted_price: bool = False
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
    related_lowest_price: Decimal | None
    offer_count: int
    in_stock_count: int
    comparable_offer_count: int
    trusted_offer_count: int = 0
    median_price: Decimal | None = None
    last_updated_at: datetime | None
    tags: list[str]


class PricePoint(BaseModel):
    observed_at: datetime
    price: Decimal | None
    stock_status: str


class DeliveryPriceSummary(BaseModel):
    delivery_type: str
    lowest_price: Decimal | None
    offer_count: int
    in_stock_count: int


class OfferGroupPublic(BaseModel):
    product_slug: str
    product_name: str
    fingerprint: str
    representative: OfferPublic
    offer_count: int
    shop_count: int
    in_stock_count: int
    lowest_price: Decimal | None
    highest_price: Decimal | None
    latest_observed_at: datetime | None


class ProductDetail(ProductCard):
    description: str
    highest_price: Decimal | None
    offer_group_count: int
    price_breakdown: list[DeliveryPriceSummary]
    snapshot_id: int | None
    snapshot_at: datetime | None
    offers: list[OfferPublic] = Field(default_factory=list)
    offer_groups: list[OfferGroupPublic] = Field(default_factory=list)
    history: list[PricePoint]


class OfferPageResponse(BaseModel):
    items: list[OfferPublic]


class OfferGroupPageResponse(BaseModel):
    items: list[OfferGroupPublic]
    total: int
    offer_total: int
    snapshot_id: int | None


class CatalogOfferGroupPageResponse(OfferGroupPageResponse):
    in_stock_count: int
    last_updated_at: datetime | None
    snapshot_at: datetime | None


class GroupOffersResponse(BaseModel):
    items: list[OfferPublic]


class OfferDescriptionResponse(BaseModel):
    offer_id: int
    original_description: str


class ShopDetail(BaseModel):
    token: str
    name: str
    source_url: str
    platform: str
    status: str
    first_seen_at: datetime
    last_success_at: datetime | None
    last_seen_at: datetime | None
    consecutive_failures: int
    offer_count: int
    offers: list[OfferPublic]


class CatalogResponse(BaseModel):
    items: list[ProductCard]
    total: int
    offer_count: int
    in_stock_count: int
    snapshot_id: int | None
    snapshot_at: datetime | None


class CatalogSnapshotPublic(BaseModel):
    id: int | None
    published_at: datetime | None


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


class ShopRequestCreate(BaseModel):
    shop_url: HttpUrl
    shop_name: str = Field(default="", max_length=120)
    contact: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=1000)


class ShopRequestOut(BaseModel):
    status: Literal["submitted", "already_pending", "already_known"]
    request_id: int | None = None
    shop_token: str


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
