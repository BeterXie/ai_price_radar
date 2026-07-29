from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(50), default="ldxp", index=True)
    source_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    raw_products: Mapped[list[RawProduct]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    offers: Mapped[list[Offer]] = relationship(back_populates="shop")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    display_name: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    product_type: Mapped[str] = mapped_column(String(60), default="other", index=True)
    search_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    offers: Mapped[list[Offer]] = relationship(back_populates="product")


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80), default="import")
    offer_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RawProduct(Base):
    __tablename__ = "raw_products"
    __table_args__ = (UniqueConstraint("shop_id", "source_product_key", name="uq_raw_shop_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    source_product_key: Mapped[str] = mapped_column(String(300))
    original_name: Mapped[str] = mapped_column(Text)
    original_category: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shop: Mapped[Shop] = relationship(back_populates="raw_products")
    offer: Mapped[Offer | None] = relationship(back_populates="raw_product", uselist=False)


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_public", "active", "approved", "stock_status", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_product_id: Mapped[int] = mapped_column(ForeignKey("raw_products.id", ondelete="CASCADE"), unique=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    stock_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    auto_delivery: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification_confidence: Mapped[int] = mapped_column(Integer, default=0)
    delivery_type: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    is_comparable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    service_period: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    warranty: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    use_scenarios: Mapped[list[str]] = mapped_column(JSON, default=list)
    item_fingerprint: Mapped[str] = mapped_column(String(64), default="", index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_snapshots.id", ondelete="SET NULL"), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    hidden_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    raw_product: Mapped[RawProduct] = relationship(back_populates="offer")
    product: Mapped[Product | None] = relationship(back_populates="offers")
    shop: Mapped[Shop] = relationship(back_populates="offers")
    history: Mapped[list[OfferHistory]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class OfferHistory(Base):
    __tablename__ = "offer_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(30), default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    offer: Mapped[Offer] = relationship(back_populates="history")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80), default="ldxp")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempted: Mapped[int] = mapped_column(Integer, default=0)
    successful: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    matches: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="correction", index=True)
    message: Mapped[str] = mapped_column(Text)
    contact: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    public_summary: Mapped[str] = mapped_column(Text, default="")
    merchant_response: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ReportRateLimit(Base):
    __tablename__ = "report_rate_limits"

    client_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
