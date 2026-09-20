from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import json
import re
import urllib.parse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .core.email import normalize_email
from .services.source_platform import normalize_public_https_url


def _normalize_skill_https_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return ""
    if re.search(r"[\x00-\x20\x7f]", cleaned):
        raise ValueError("skill URL contains invalid whitespace or control characters")
    parsed = urllib.parse.urlsplit(cleaned)
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("skill URL must be an HTTPS URL without credentials")
    return cleaned


def _normalize_skill_demo_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return ""
    if re.search(r"[\x00-\x20\x7f\\]", cleaned):
        raise ValueError("demo URL contains invalid characters")
    parsed = urllib.parse.urlsplit(cleaned)
    decoded_path = urllib.parse.unquote(parsed.path)
    segments = decoded_path.split("/")
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not decoded_path.startswith("/demos/")
        or not decoded_path.endswith(".html")
        or any(segment in {".", ".."} for segment in segments)
    ):
        raise ValueError("demo URL must be a local /demos/*.html path")
    return cleaned


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
    click_count: int = 0
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
    click_count: int = 0
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
    history: list[PricePoint] = Field(default_factory=list)
    trend: list[PriceTrendPoint] = Field(default_factory=list)


class ProductHistoryResponse(BaseModel):
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


class ShopProduct(BaseModel):
    """A standard product represented by a shop's current public offers."""

    slug: str
    display_name: str
    offer_count: int
    in_stock_count: int


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
    today_clicks: int = 0
    total_clicks: int = 0
    products: list[ShopProduct] = Field(default_factory=list)
    offers: list[OfferPublic]


class OfferClickResponse(BaseModel):
    success: bool = True
    recorded: bool = True
    click_count: int = 0


class ShopCard(BaseModel):
    """Lightweight shop summary for directory listings and SEO pages."""

    token: str
    name: str
    source_url: str
    source_platform: str
    source_platform_label: str
    offer_count: int
    in_stock_count: int
    product_count: int
    first_seen_at: datetime
    last_seen_at: datetime | None
    last_success_at: datetime | None
    product_slugs: list[str] = Field(default_factory=list)


class ShopListResponse(BaseModel):
    items: list[ShopCard]
    total: int


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


class SiteNoticeOut(BaseModel):
    enabled: bool = True
    badge: str = "最新动态"
    title: str = ""
    content: str = ""
    link_text: str = ""
    link_url: str = ""


class CommunityNoticeOut(BaseModel):
    enabled: bool = True
    title: str = "加入 AI 比价交流群"
    desc: str = "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。"
    qq_group: str = "938741334"
    qq_url: str = ""
    btn_text: str = "一键加入 QQ 群"


class MetaResponse(BaseModel):
    platforms: list[str]
    brands: list[str]
    source_platforms: list[SourcePlatformMeta]
    product_types: list[str]
    tags: list[str]
    advertise_enabled: bool = False
    bot_enabled: bool = True
    site_notice: SiteNoticeOut | None = None
    community_notice: CommunityNoticeOut | None = None


class ReportCreate(BaseModel):
    offer_id: int | None = None
    product_slug: str | None = Field(default=None, max_length=160, pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: Literal["correction", "unavailable", "fraud_concern", "shop_request", "other"] = "correction"
    message: str = Field(min_length=10, max_length=2000)
    contact: str = Field(default="", max_length=200)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int | None
    product_slug: str | None
    kind: str
    message: str
    contact: str
    status: str
    public_summary: str = ""
    merchant_response: str = ""
    resolved_at: datetime | None = None
    created_at: datetime


class ShopRequestCreate(BaseModel):
    source_type: Literal[
        "auto", "ldxp", "dujiao_next", "merchant_json", "merchant_feed", "16688",
        "woocommerce", "schema_org", "other",
    ] = "auto"
    declared_platform: Literal[
        "auto", "ldxp", "dujiao_next", "merchant_json", "merchant_feed", "16688",
        "woocommerce", "schema_org", "other",
    ] | None = None
    shop_url: HttpUrl
    shop_name: str = Field(default="", max_length=120)
    contact: str = Field(min_length=3, max_length=200)
    note: str = Field(default="", max_length=1000)
    authorization_confirmed: Literal[True]
    consent_version: Literal["shop-source-submission-v1"]

    @field_validator("contact")
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("shop_name")
    @classmethod
    def validate_shop_name(cls, value: str) -> str:
        cleaned = re.sub(r"[\r\n\t\x00-\x1f\x7f]+", " ", str(value or "")).strip()
        cleaned = cleaned.replace("<", "").replace(">", "").strip()
        cleaned = re.sub(r" +", " ", cleaned)
        return cleaned

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", "", str(value or "")).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned



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


class SourceIntakeUpdatePlatform(BaseModel):
    platform: Literal["ldxp", "dujiao_next", "woocommerce", "16688", "merchant_json", "schema_org", "other"]


class SourceIntakeApprove(BaseModel):
    platform: Literal["ldxp", "dujiao_next", "woocommerce", "16688", "merchant_json", "schema_org", "other"] | None = None



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
    detected_platform: Literal[
        "ldxp", "dujiao_next", "merchant_json", "woocommerce", "16688", "schema_org", "other", "unknown",
    ] = "unknown"
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


class DiscoveryRunCreate(BaseModel):
    trigger: Literal["scheduled", "manual", "deploy"] = "scheduled"
    adapters: list[str] = Field(default_factory=list, max_length=20)


class DiscoveryRunFinish(BaseModel):
    status: Literal["succeeded", "partial", "failed"]
    discovered_raw_count: int = Field(default=0, ge=0)
    normalized_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    new_candidate_count: int = Field(default=0, ge=0)
    reverified_count: int = Field(default=0, ge=0)
    detected_count: int = Field(default=0, ge=0)
    ai_matched_count: int = Field(default=0, ge=0)
    auto_approved_count: int = Field(default=0, ge=0)
    pending_review_count: int = Field(default=0, ge=0)
    validation_failed_count: int = Field(default=0, ge=0)
    promoted_intake_count: int = Field(default=0, ge=0)
    adapter_stats: dict[str, int] = Field(default_factory=dict)
    platform_stats: dict[str, int] = Field(default_factory=dict)
    failure_stats: dict[str, int] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)


class DiscoveryCandidateUpsert(BaseModel):
    run_id: int | None = None
    discovered_url: str = Field(min_length=1, max_length=2000)
    platform_hint: str = Field(default="unknown", max_length=30)
    discovered_by: str = Field(min_length=1, max_length=100)
    matched_query: str = Field(default="", max_length=300)


class DiscoveryCandidateBatch(BaseModel):
    items: list[DiscoveryCandidateUpsert] = Field(min_length=1, max_length=100)


class DiscoveryCandidateClaimRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    lease_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)


class DiscoveryCandidateClaimOut(BaseModel):
    candidate_id: int
    candidate_key: str
    canonical_url: str
    platform_hint: str
    attempt_count: int
    lease_expires_at: datetime


class DiscoveryCandidateResult(BaseModel):
    status: Literal["detected", "no_match", "validation_failed"]
    attempt_count: int = Field(ge=1)
    detected_platform: str = Field(default="unknown", max_length=30)
    detected_source_key: str = Field(default="", max_length=300)
    detected_source_url: str = Field(default="", max_length=2000)
    total_product_count: int = Field(default=0, ge=0)
    ai_product_count: int = Field(default=0, ge=0)
    sample_products: list[dict[str, object]] = Field(default_factory=list, max_length=5)
    fingerprints: list[str] = Field(default_factory=list, max_length=50)
    confidence_score: int = Field(default=0, ge=0, le=100)
    failure_reason: str = Field(default="", max_length=500)


class SourceCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_key: str
    canonical_origin: str
    discovered_url: str
    canonical_url: str
    platform_hint: str
    detected_platform: str
    detected_source_key: str
    detected_source_url: str
    discovery_sources: list[str]
    matched_queries: list[str]
    fingerprints: list[str]
    sample_products: list[dict[str, object]]
    total_product_count: int
    ai_product_count: int
    confidence_score: int
    status: str
    failure_reason: str
    decision_note: str
    attempt_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    last_verified_at: datetime | None
    next_verify_at: datetime | None
    lease_expires_at: datetime | None
    promoted_intake_id: int | None
    discovery_run_id: int | None
    created_at: datetime
    updated_at: datetime


class SourceDiscoveryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger: str
    adapters: list[str]
    status: str
    started_at: datetime
    finished_at: datetime | None
    discovered_raw_count: int
    normalized_count: int
    duplicate_count: int
    new_candidate_count: int
    reverified_count: int
    detected_count: int
    ai_matched_count: int
    auto_approved_count: int
    pending_review_count: int
    validation_failed_count: int
    promoted_intake_count: int
    adapter_stats: dict[str, int]
    platform_stats: dict[str, int]
    failure_stats: dict[str, int]
    note: str
    created_at: datetime


class SourceCandidateAction(BaseModel):
    reason: str = Field(default="", max_length=500)


class SourceCandidateCleanupRequest(BaseModel):
    statuses: list[str] = Field(
        default_factory=lambda: ["no_match", "validation_failed", "disabled"]
    )


class SourceCandidateCleanupOut(BaseModel):
    deleted_count: int
    statuses: list[str]


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

    @field_validator("approved", "active")
    @classmethod
    def reject_null_flags(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("offer flags cannot be null")
        return value

    @field_validator("hidden_reason")
    @classmethod
    def clear_hidden_reason(cls, value: str | None) -> str:
        return value or ""


class AdminReportUpdate(BaseModel):
    status: Literal["open", "reviewing", "resolved", "rejected"]
    public_summary: str | None = Field(default=None, max_length=500)
    merchant_response: str | None = Field(default=None, max_length=1000)


class AdminStats(BaseModel):
    shops: int
    products: int
    offers: int
    public_offers: int
    restricted_offers: int = 0
    unclassified_offers: int = 0
    open_corrections: int
    pending_source_intakes: int
    # Backward-compatible alias; the UI uses the explicit fields above.
    open_reports: int
    total_users: int = 0
    last_scan_at: datetime | None
    product_counts: dict[str, int] = Field(default_factory=dict)
    brand_counts: dict[str, int] = Field(default_factory=dict)


class AdminSettingsOut(BaseModel):
    advertise_enabled: bool = False
    bot_enabled: bool = True
    site_notice_enabled: bool = True
    site_notice_badge: str = "最新动态"
    site_notice_title: str = ""
    site_notice_content: str = ""
    site_notice_link_text: str = ""
    site_notice_link_url: str = ""
    community_enabled: bool = True
    community_title: str = "加入 AI 比价交流群"
    community_desc: str = "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。"
    community_qq_group: str = "938741334"
    community_qq_url: str = ""
    community_btn_text: str = "一键加入 QQ 群"


class AdminSettingsUpdate(BaseModel):
    advertise_enabled: bool | None = None
    bot_enabled: bool | None = None
    site_notice_enabled: bool | None = None
    site_notice_badge: str | None = None
    site_notice_title: str | None = None
    site_notice_content: str | None = None
    site_notice_link_text: str | None = None
    site_notice_link_url: str | None = None
    community_enabled: bool | None = None
    community_title: str | None = None
    community_desc: str | None = None
    community_qq_group: str | None = None
    community_qq_url: str | None = None
    community_btn_text: str | None = None

    @field_validator("site_notice_link_url", "community_qq_url")
    @classmethod
    def validate_public_link(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return ""
        if re.search(r"[\x00-\x20\x7f]", cleaned):
            raise ValueError("link URL contains invalid whitespace or control characters")
        if info.field_name == "site_notice_link_url":
            if not cleaned.startswith("/") or cleaned.startswith("//"):
                raise ValueError("site notice link must be an internal path")
            decoded = urllib.parse.unquote(cleaned)
            path = decoded.split("?", 1)[0].split("#", 1)[0]
            if "\\" in decoded or any(segment in {".", ".."} for segment in path.split("/")):
                raise ValueError("internal link URL is invalid")
            parsed_internal = urllib.parse.urlsplit(cleaned)
            if parsed_internal.scheme or parsed_internal.netloc:
                raise ValueError("site notice link must be an internal path")
            return cleaned
        parsed = urllib.parse.urlsplit(cleaned)
        if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("link URL must be an internal path or public HTTPS URL")
        return cleaned


class CommunitySkillSummaryOut(BaseModel):
    id: int
    slug: str
    kind: str
    title: str
    subtitle: str = ""
    summary: str = ""
    author_name: str = ""
    author_url: str = ""
    repo_url: str = ""
    stars_count: int = 0
    install_command: str = ""
    prompt_template: str = ""
    demo_url: str = ""
    demo_type: str = "none"

    tags: list[str] = Field(default_factory=list)
    target_models: list[str] = Field(default_factory=list)
    related_product_slug: str | None = None
    is_pinned: bool = False
    is_visible: bool = True
    sort_order: int = 0
    view_count: int = 0
    copy_count: int = 0
    created_at: datetime
    updated_at: datetime


class RelatedProductSummary(BaseModel):
    slug: str
    platform: str
    display_name: str
    subtitle: str = ""
    product_type: str = "other"


class CommunitySkillDetailOut(CommunitySkillSummaryOut):
    content_markdown: str = ""
    prompt_template: str = ""
    related_product: RelatedProductSummary | None = None



class CommunitySkillPageOut(BaseModel):
    items: list[CommunitySkillSummaryOut]
    total: int
    page: int
    page_size: int
    kinds: list[str] = Field(default_factory=list)
    all_tags: list[str] = Field(default_factory=list)


class AdminCommunitySkillCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="skill", max_length=40)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=1000)
    content_markdown: str = Field(default="")
    prompt_template: str = Field(default="")
    author_name: str = Field(default="", max_length=100)
    author_url: str = Field(default="", max_length=500)
    repo_url: str = Field(default="", max_length=500)
    stars_count: int = Field(default=0, ge=0)
    install_command: str = Field(default="", max_length=1000)
    demo_url: str = Field(default="", max_length=500)
    demo_type: str = Field(default="none", max_length=40)
    tags: list[str] = Field(default_factory=list)
    target_models: list[str] = Field(default_factory=list)
    related_product_slug: str | None = Field(default=None, max_length=160)
    is_pinned: bool = False
    is_visible: bool = True
    sort_order: int = 0

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        cleaned = value.strip().casefold()
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", cleaned) is None:
            raise ValueError("slug must contain lowercase letters, numbers, and single hyphens only")
        return cleaned

    @field_validator("author_url", "repo_url")
    @classmethod
    def validate_https_urls(cls, value: str) -> str:
        return _normalize_skill_https_url(value) or ""

    @field_validator("demo_url")
    @classmethod
    def validate_demo_url(cls, value: str) -> str:
        return _normalize_skill_demo_url(value) or ""


class AdminCommunitySkillUpdate(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    kind: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=1000)
    content_markdown: str | None = None
    prompt_template: str | None = None
    author_name: str | None = Field(default=None, max_length=100)
    author_url: str | None = Field(default=None, max_length=500)
    repo_url: str | None = Field(default=None, max_length=500)
    stars_count: int | None = Field(default=None, ge=0)
    install_command: str | None = Field(default=None, max_length=1000)
    demo_url: str | None = Field(default=None, max_length=500)
    demo_type: str | None = Field(default=None, max_length=40)
    tags: list[str] | None = None
    target_models: list[str] | None = None
    related_product_slug: str | None = Field(default=None, max_length=160)
    is_pinned: bool | None = None
    is_visible: bool | None = None
    sort_order: int | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().casefold()
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", cleaned) is None:
            raise ValueError("slug must contain lowercase letters, numbers, and single hyphens only")
        return cleaned

    @field_validator("author_url", "repo_url")
    @classmethod
    def validate_https_urls(cls, value: str | None) -> str | None:
        return _normalize_skill_https_url(value)

    @field_validator("demo_url")
    @classmethod
    def validate_demo_url(cls, value: str | None) -> str | None:
        return _normalize_skill_demo_url(value)

    @field_validator(
        "kind",
        "title",
        "subtitle",
        "summary",
        "content_markdown",
        "prompt_template",
        "author_name",
        "author_url",
        "repo_url",
        "stars_count",
        "install_command",
        "demo_url",
        "demo_type",
        "tags",
        "target_models",
        "is_pinned",
        "is_visible",
        "sort_order",
    )
    @classmethod
    def reject_null_non_nullable_fields(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class UserRead(BaseModel):
    id: int
    email: str | None = None
    nickname: str = ""
    avatar_url: str = ""
    has_qq_bound: bool = False
    created_at: datetime


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        return normalize_email(value)


class EmailCodeResponse(BaseModel):
    success: bool
    retry_after: int = 60
    message: str


class EmailVerifyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    code: str = Field(pattern=r"^\d{6}$")

    @field_validator("email")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        return normalize_email(value)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: UserRead | None = None


class UserBotBindingRead(BaseModel):
    id: int
    channel: str
    target_id: str
    is_active: bool
    notify_price_drop: bool
    notify_price_hike: bool
    created_at: datetime


class UserBotBindingUpdate(BaseModel):
    is_active: bool | None = None
    notify_price_drop: bool | None = None
    notify_price_hike: bool | None = None


class QQBotBindingStartResponse(BaseModel):
    session_id: str
    bind_code: str
    qrcode_url: str = ""
    expires_in_seconds: int = 300
    instruction: str = "请使用手机 QQ 扫描二维码进行授权绑定"


class BotCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    channel: str = Field(default="qq", max_length=30)
    sender_id: str = Field(default="", max_length=100)


class BotCommandResponse(BaseModel):
    reply: str


class UserSubscriptionRead(BaseModel):
    id: int
    product_slug: str
    product_name: str
    platform: str
    target_price: Decimal | None = None
    current_min_price: Decimal | None = None
    current_currency: str = "CNY"
    stock_count: int = 0
    notify_email: bool
    notify_bot: bool
    created_at: datetime
    updated_at: datetime


class UserSubscriptionCreateOrUpdate(BaseModel):
    product_slug: str = Field(min_length=1, max_length=120)
    target_price: Decimal | None = Field(default=None, ge=0, le=Decimal("99999999.99"), max_digits=10, decimal_places=2)
    notify_email: bool = True
    notify_bot: bool = True


class UserSubscriptionPatch(BaseModel):
    target_price: Decimal | None = Field(default=None, ge=0, le=Decimal("99999999.99"), max_digits=10, decimal_places=2)
    notify_email: bool | None = None
    notify_bot: bool | None = None


class UserSubscriptionListOut(BaseModel):
    items: list[UserSubscriptionRead]
    count: int
    email_bound: bool
    bot_bound: bool


class CouponRead(BaseModel):
    id: int
    name: str
    code: str
    discount_amount: Decimal
    min_spend: Decimal
    shop_name: str
    shop_url: str
    shop_id: int | None = None
    is_assigned: bool
    assigned_at: datetime | None = None
    expires_at: datetime
    is_used: bool = False
    created_at: datetime
    coupon_batch_id: int = 0
    campaign_id: int | None = None


class UserCouponListOut(BaseModel):
    items: list[CouponRead]
    count: int


class CouponRedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class CouponClaimResponse(BaseModel):
    success: bool
    message: str
    coupon: CouponRead | None = None


class CampaignRead(BaseModel):
    id: int
    campaign_code: str
    title: str
    coupon_batch_id: int
    shop_id: int | None = None
    shop_url: str | None = None
    shop_name: str | None = None
    max_per_user: int
    total_quota: int
    claimed_count: int
    is_active: bool
    expires_at: datetime
    created_at: datetime


class CouponDropStatus(BaseModel):
    enabled: bool
    probability: int
    has_stock: bool
    remaining_stock: int


class CouponDropQualificationResponse(BaseModel):
    success: bool = True
    eligible: bool = False
    claim_token: str = ""


class CouponDropClaimRequest(BaseModel):
    claim_token: str = Field(min_length=20, max_length=2000)


class CouponDropTrackRequest(BaseModel):
    page: str = Field(default="", max_length=200)
    extra_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extra_data")
    @classmethod
    def validate_extra_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 20:
            raise ValueError("extra_data contains too many keys")
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 4096:
            raise ValueError("extra_data is too large")
        return value


class AdminCouponStats(BaseModel):
    total_coupons: int
    assigned_coupons: int
    unassigned_coupons: int
    used_coupons: int
    total_campaigns: int
    drop_enabled: bool
    drop_probability: int
    dynamic_drop: bool
    daily_drop_limit: int
    drop_trigger_count: int = 0


class AdminCouponSettingsUpdate(BaseModel):
    drop_enabled: bool | None = None
    drop_probability: int | None = Field(default=None, ge=0, le=100)
    dynamic_drop: bool | None = None
    daily_drop_limit: int | None = Field(default=None, ge=1, le=1000)


class AdminCouponImportRequest(BaseModel):
    name: str = "专享立减券"
    discount_amount: Decimal = Field(default=Decimal("5.00"), gt=0, max_digits=10, decimal_places=2)
    min_spend: Decimal = Field(default=Decimal("15.00"), ge=0, max_digits=10, decimal_places=2)
    expires_at: datetime | None = None
    shop_name: str = ""
    shop_url: str = ""
    shop_id: int | None = None
    coupon_batch_id: int = 0
    codes_text: str = Field(min_length=1)

    @field_validator("shop_url")
    @classmethod
    def validate_shop_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        try:
            return normalize_public_https_url(cleaned)
        except ValueError as exc:
            raise ValueError("shop_url must be a public HTTPS URL") from exc

    @field_validator("expires_at")
    @classmethod
    def validate_future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if normalized.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return normalized


class AdminCouponSyncRequest(BaseModel):
    # Merchant API token; sent in the body (not the URL) so it never lands in
    # access logs or reverse-proxy logs.
    token: str = Field(default="", max_length=200)


class AdminCouponImportResponse(BaseModel):
    success: bool
    imported_count: int
    skipped_count: int
    message: str


class AdminCouponPageOut(BaseModel):
    items: list[CouponRead]
    total: int
    page: int
    page_size: int


class AdminCampaignCreate(BaseModel):
    campaign_code: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=120)
    coupon_batch_id: int = 0
    shop_id: int | None = None
    shop_url: str | None = None
    shop_name: str | None = None
    max_per_user: int = Field(default=1, ge=1)
    total_quota: int = Field(default=100, ge=1)
    expires_at: datetime | None = None

    @field_validator("shop_url")
    @classmethod
    def validate_shop_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return normalize_public_https_url(cleaned)
        except ValueError as exc:
            raise ValueError("shop_url must be a public HTTPS URL") from exc

    @field_validator("expires_at")
    @classmethod
    def validate_future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if normalized.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return normalized


class AdminUserItem(BaseModel):
    id: int
    email: str | None = None
    nickname: str = ""
    avatar_url: str = ""
    has_qq_bound: bool = False
    has_bot_bound: bool = False
    bot_channel: str | None = None
    bot_target_id: str | None = None
    bot_active: bool = False
    is_active: bool = True
    created_at: datetime
    last_login_at: datetime | None = None
    last_login_ip: str = ""
    last_active_at: datetime | None = None
    session_duration_seconds: int = 0
    total_duration_seconds: int = 0
    is_online: bool = False
    button_click_count: int = 0
    coupon_count: int = 0
    active_coupon_count: int = 0
    used_coupon_count: int = 0


class AdminUserPageOut(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    limit: int


class AdminUserStatsOut(BaseModel):
    total_users: int = 0
    active_today: int = 0
    active_7d: int = 0
    online_now: int = 0
    total_clicks: int = 0
    total_coupons_held: int = 0


class AdminUserSessionItem(BaseModel):
    token: str
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime
    last_active_at: datetime | None = None
    duration_seconds: int = 0
    is_active: bool = False


class AdminUserActionLogItem(BaseModel):
    id: int
    action_type: str
    action_name: str
    target_id: str = ""
    page: str = ""
    ip_address: str = ""
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AdminUserDetailOut(BaseModel):
    user: AdminUserItem
    sessions: list[AdminUserSessionItem] = Field(default_factory=list)
    coupons: list[CouponRead] = Field(default_factory=list)
    action_logs: list[AdminUserActionLogItem] = Field(default_factory=list)
    bot_bindings: list[UserBotBindingRead] = Field(default_factory=list)
    subscription_count: int = 0


class AdminBroadcastCreate(BaseModel):
    operation_key: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    channels: list[Literal["email", "bot"]] = Field(
        default_factory=lambda: ["email", "bot"], min_length=1, max_length=2
    )

    @field_validator("title", "content")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("broadcast text must not be blank")
        return cleaned

    @field_validator("channels")
    @classmethod
    def validate_unique_channels(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("broadcast channels must be unique")
        return value


class AdminUserStatusUpdate(BaseModel):
    is_active: bool = Field(strict=True)


class AdminBroadcastItem(BaseModel):
    id: int
    operation_key: str
    title: str
    content: str
    channels: list[str] = Field(default_factory=list)
    target_user_count: int = 0
    email_sent_count: int = 0
    bot_sent_count: int = 0
    status: str = "sent"
    created_by: str = "admin"
    created_at: datetime


class AdminBroadcastAudienceOut(BaseModel):
    total_users: int = 0
    email_users: int = 0
    bot_users: int = 0
    total_reach: int = 0


class UserTrackClickRequest(BaseModel):
    button_name: str = Field(min_length=1, max_length=100)
    button_id: str = Field(default="", max_length=100)
    page: str = Field(default="", max_length=200)
    target_url: str = Field(default="", max_length=500)
    extra_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extra_data")
    @classmethod
    def validate_extra_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 20:
            raise ValueError("extra_data contains too many keys")
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 4096:
            raise ValueError("extra_data is too large")
        return value


class UserHeartbeatResponse(BaseModel):
    status: str = "ok"
    online_seconds: int = 0
    is_online: bool = True
