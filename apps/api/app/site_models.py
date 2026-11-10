"""Editorial data owned by a brand; crawled products and snapshots remain shared."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import utcnow


class SiteArticle(Base):
    __tablename__ = "site_articles"
    __table_args__ = (UniqueConstraint("site_id", "slug"), Index("ix_site_articles_publication", "site_id", "status", "published_at"))

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[str] = mapped_column(String(32))
    slug: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    author: Mapped[str] = mapped_column(String(100), default="")
    markdown: Mapped[str] = mapped_column(Text)
    seo_title: Mapped[str] = mapped_column(String(160), default="")
    seo_description: Mapped[str] = mapped_column(String(280), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SiteRelay(Base):
    __tablename__ = "site_relays"

    site_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("relay_stations.id", ondelete="CASCADE"), primary_key=True)
    tagline: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(default=100)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    is_sponsored: Mapped[bool] = mapped_column(default=False)
    click_count: Mapped[int] = mapped_column(default=0)


class SiteAd(Base):
    __tablename__ = "site_ads"
    __table_args__ = (Index("ix_site_ads_placement", "site_id", "placement", "is_enabled"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[str] = mapped_column(String(32))
    placement: Mapped[str] = mapped_column(String(40), default="home_hero")
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    sponsor_name: Mapped[str] = mapped_column(String(100), default="")
    badge: Mapped[str] = mapped_column(String(20), default="广告")
    cta_text: Mapped[str] = mapped_column(String(40), default="了解详情")
    link_url: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(default=100)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
