from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class OfficialPriceReferencePublic(BaseModel):
    provider: str
    plan: str
    price: Decimal | None
    currency: str
    billing_period: str
    url: str
    checked_at: date
    note: str


class SourceHealthPublic(BaseModel):
    score: int = Field(ge=0, le=100)
    label: str
    reasons: list[str]


class PriceTrendPoint(BaseModel):
    bucket_at: datetime
    price_currency: str
    trusted_lowest_price: Decimal | None
    median_price: Decimal | None
    in_stock_count: int
    observation_count: int


class OfferPublic(BaseModel):
    id: int
    shop_token: str
    shop_name: str
    source_platform: str
    source_platform_label: str
    source_kind: str
    source_kind_label: str
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
    source_health: SourceHealthPublic
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    observed_at: datetime


class ProductCard(BaseModel):
    slug: str
    platform: str
    brand: str
    display_name: str
    subtitle: str
    product_type: str
    price_currency: str
    lowest_price: Decimal | None
    related_lowest_price: Decimal | None
    offer_count: int
    in_stock_count: int
    comparable_offer_count: int
    trusted_offer_count: int = 0
    median_price: Decimal | None = None
    source_count: int = 0
    data_quality_score: int = Field(default=0, ge=0, le=100)
    data_quality_label: str = "数据不足"
    official_reference: OfficialPriceReferencePublic | None = None
    last_updated_at: datetime | None
    tags: list[str]


class PricePoint(BaseModel):
    observed_at: datetime
    price: Decimal | None
    currency: str
    stock_status: str


class DeliveryPriceSummary(BaseModel):
    delivery_type: str
    price_currency: str
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
    price_currency: str
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
    trend: list[PriceTrendPoint] = Field(default_factory=list)


class OfferPageResponse(BaseModel):
    items: list[OfferPublic]


class OfferGroupPageResponse(BaseModel):
    items: list[OfferGroupPublic]
    total: int
    offer_total: int
    snapshot_id: int | None


class CatalogOfferGroupPageResponse(OfferGroupPageResponse):
    in_stock_count: int
    comparable_offer_count: int = 0
    trusted_offer_count: int = 0
    metrics_note: str = "统计范围为当前筛选条件、当前已发布快照和有效时间窗口。"
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
    source_platform: str
    source_platform_label: str
    source_kind: str
    source_kind_label: str
    status: str
    first_seen_at: datetime
    last_success_at: datetime | None
    last_seen_at: datetime | None
    consecutive_failures: int
    source_health: SourceHealthPublic
    offer_count: int
    offers: list[OfferPublic]


class CatalogResponse(BaseModel):
    items: list[ProductCard]
    total: int
    offer_count: int
    in_stock_count: int
    comparable_offer_count: int = 0
    trusted_offer_count: int = 0
    metrics_note: str = "统计范围为当前筛选条件、当前已发布快照和有效时间窗口。"
    snapshot_id: int | None
    snapshot_at: datetime | None


class CatalogSnapshotPublic(BaseModel):
    id: int | None
    published_at: datetime | None


class SourcePlatformMeta(BaseModel):
    id: str
    label: str


class MetaResponse(BaseModel):
    platforms: list[str]
    brands: list[str]
    source_platforms: list[SourcePlatformMeta]
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
    public_summary: str = ""
    merchant_response: str = ""
    resolved_at: datetime | None = None
    created_at: datetime


class ShopRequestCreate(BaseModel):
    source_type: Literal["auto", "ldxp", "dujiao_next", "merchant_json", "merchant_feed", "other"] = "auto"
    declared_platform: Literal["auto", "ldxp", "dujiao_next", "merchant_json", "merchant_feed", "other"] | None = None
    shop_url: HttpUrl
    shop_name: str = Field(default="", max_length=120)
    contact: str = Field(min_length=3, max_length=200)
    note: str = Field(default="", max_length=1000)

    @field_validator("contact")
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is None:
            raise ValueError("contact must be a valid email address")
        return value


class ShopRequestOut(BaseModel):
    source_type: str
    declared_platform: str
    detected_platform: str
    detection_message: str = ""
    workflow_status: str
    status: Literal["submitted", "already_pending", "already_known"]
    request_id: int | None = None
    shop_token: str


class SourceIntakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int | None
    source_type: str
    declared_platform: str
    detected_platform: str
    workflow_status: str
    source_key: str
    source_url: str
    shop_name: str
    contact_email: str
    note: str
    origin: str
    status: str
    decision_note: str
    failure_reason: str
    attempt_count: int
    product_count: int
    lease_expires_at: datetime | None
    approved_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    email_status: dict[str, str] = Field(default_factory=dict)


class SourceIntakeReject(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rejection reason is required")
        return value


class SourceIntakeClaimRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    lease_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)


class SourceDetectionClaimRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    lease_seconds: int = Field(default=300, ge=30, le=30 * 60)


class SourceDetectionClaimOut(BaseModel):
    intake_id: int
    source_url: str
    declared_platform: str
    attempt_count: int
    lease_expires_at: datetime


class SourceDetectionResult(BaseModel):
    status: Literal["pending_review", "validation_failed"]
    attempt_count: int = Field(ge=1)
    detected_platform: Literal["ldxp", "dujiao_next", "merchant_json", "other", "unknown"] = "unknown"
    source_url: str = Field(default="", max_length=2000)
    source_key: str = Field(default="", max_length=300)
    shop_name: str = Field(default="", max_length=120)
    product_count: int = Field(default=0, ge=0)
    failure_reason: str = Field(default="", max_length=500)


class SourceIntakeClaimOut(BaseModel):
    intake_id: int
    source_type: Literal["ldxp"]
    source_key: str
    source_url: str
    shop_name: str
    attempt_count: int
    lease_expires_at: datetime


class SourceIntakeResult(BaseModel):
    status: Literal["validated", "no_products", "validation_failed", "onboarded"]
    attempt_count: int = Field(ge=1)
    product_count: int = Field(default=0, ge=0)
    failure_reason: str = Field(default="", max_length=500)
    published: bool = False

    @field_validator("failure_reason")
    @classmethod
    def normalize_failure_reason(cls, value: str) -> str:
        return " ".join(value.split())[:500]


class NotificationOutboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    recipient: str
    subject: str
    status: str
    attempt_count: int
    next_attempt_at: datetime
    last_error: str
    dedupe_key: str
    created_at: datetime
    sent_at: datetime | None


class PublicCorrection(BaseModel):
    id: int
    offer_id: int | None
    kind: str
    public_summary: str
    merchant_response: str
    resolved_at: datetime | None
    created_at: datetime


class PublicCorrectionPage(BaseModel):
    items: list[PublicCorrection]
    total: int



class AdminOfferUpdate(BaseModel):
    approved: bool | None = None
    active: bool | None = None
    product_slug: str | None = None
    hidden_reason: str | None = Field(default=None, max_length=500)


class AdminReportUpdate(BaseModel):
    status: Literal["open", "reviewing", "resolved", "rejected"]
    public_summary: str | None = Field(default=None, max_length=500)
    merchant_response: str | None = Field(default=None, max_length=1000)


class AdminStats(BaseModel):
    shops: int
    products: int
    offers: int
    public_offers: int
    open_corrections: int
    pending_source_intakes: int
    # Backward-compatible alias; the UI uses the explicit fields above.
    open_reports: int
    last_scan_at: datetime | None
