from __future__ import annotations

import json
import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from currencies import normalize_currency


class Base(DeclarativeBase):
    pass


class ImportLockUnavailable(RuntimeError):
    pass


@contextmanager
def import_lock(db: Session):
    """Serialize import transactions that target the same PostgreSQL database."""
    if db.get_bind().dialect.name != "postgresql":
        yield
        return
    acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": 0x415052494D504F52},
    ).scalar_one()
    if not acquired:
        raise ImportLockUnavailable("another catalog import is already running")
    yield


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Shop(Base):
    __tablename__ = "shops"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(50), default="ldxp")
    source_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    platform: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    product_type: Mapped[str] = mapped_column(String(60), default="other")
    search_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80), default="import")
    offer_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RawProduct(Base):
    __tablename__ = "raw_products"
    __table_args__ = (UniqueConstraint("shop_id", "source_product_key", name="uq_raw_shop_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    source_product_key: Mapped[str] = mapped_column(String(300))
    original_name: Mapped[str] = mapped_column(Text)
    original_category: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_product_id: Mapped[int] = mapped_column(ForeignKey("raw_products.id", ondelete="CASCADE"), unique=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    stock_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(30), default="unknown")
    auto_delivery: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification_confidence: Mapped[int] = mapped_column(Integer, default=0)
    delivery_type: Mapped[str] = mapped_column(String(40), default="unknown")
    is_comparable: Mapped[bool] = mapped_column(Boolean, default=False)
    service_period: Mapped[str] = mapped_column(String(40), default="unknown")
    warranty: Mapped[str] = mapped_column(String(40), default="unknown")
    use_scenarios: Mapped[list[str]] = mapped_column(JSON, default=list)
    item_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_snapshots.id", ondelete="SET NULL"), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    hidden_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfferHistory(Base):
    __tablename__ = "offer_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    stock_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str] = mapped_column(String(30), default="unknown")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


BRAND_MARKERS = {
    "chatgpt": ["chatgpt", "chat gpt", "openai", "open ai", "gpt", "chat plus"],
    "codex": ["codex"],
    "claude": ["claude"],
    "gemini": ["gemini", "google one ai"],
    "grok": ["supergrok", "super grok", "grok", "x.ai", "x ai", "xai"],
    "x": ["x premium", "xpremium", "twitter", "推特"],
}
CHATGPT_API_MARKERS = ["openai api", "open ai api", "gpt api", "api额度", "api 额度", "api余额", "api 余额", "api key", "apikey"]
CHATGPT_K12_MARKERS = ["chatgpt team", "gpt team", "business", "k12", "团队", "车位", "母号", "自动拉", "团队邀请"]
CHATGPT_PRO_MARKERS = ["chatgpt pro", "gpt pro", "200刀"]
CHATGPT_PLUS_MARKERS = ["chatgpt plus", "gpt plus", "chat plus", "plus", "puls", "plsu"]
CHATGPT_GO_MARKERS = ["chatgpt go", "gpt go", "go会员", "go订阅"]
CHATGPT_FREE_MARKERS = ["chatgpt free", "gpt free", "free账号", "free号", "免费账号", "普通账号", "普通号", "普号", "不含plus", "不含 plus", "不是plus", "不是 plus", "非plus", "非 plus", "无plus", "无 plus"]
CHATGPT_NON_PRODUCT_MARKERS = ["镜像站", "教程", "使用指南", "购买指南", "攻略", "授权神器", "自动化授权"]
CHATGPT_AMBIGUOUS_CREDIT_MARKERS = ["刀额度", "美元额度"]
IMPLICIT_CHATGPT_MARKERS = ["成品", "半成品", "首登"]
NON_TARGET_PLUS_MARKERS = ["百度", "网盘", "小红书", "加速器", "梯子", "夸克", "迅雷", "youtube", "netflix", "spotify", "office", "wps"]
PLATFORM_16688 = "16688"
RELAY_MARKERS = ["中转", "反代", "sub2api", "倍率"]
SHARED_POOL_MARKERS = ["号池", "共享池", "共享号", "拼车池"]
TRIAL_MARKERS = ["日抛", "体验版", "体验号", "试用号", "小时号"]
GENERIC_EMAIL_MARKERS = ["gmail", "谷歌邮箱", "谷歌邮件", "谷歌账号", "outlook", "hotmail", "icloud", "ic邮箱", "微软邮箱"]
CATEGORY_COMMERCE_MARKERS = ["plus", "pro", "team", "business", "max", "advanced", "ultra", "super", "heavy", "会员", "订阅", "代充", "直充", "充值", "接码", "api", "key", "token", "额度", "成品", "账号", "首登"]
CHATGPT_SERVICE_MARKERS = ["接码", "验证码", "短信验证", "手机验证", "提链", "扫码对接", "二维码生成", "cyber认证", "persona认证"]
CHATGPT_PRODUCT_MARKERS = ["成品", "账号", "已注册", "会员", "订阅", "代充", "直充", "充值"]
CHATGPT_EXPLICIT_PRODUCT_MARKERS = ["成品", "半成品", "账号", "已注册", "会员", "充值", "代充", "直充", "卡密", "cdk", "兑换码"]
TAG_RULES = {
    "Team": ["team", "团队", "车位"], "Business": ["business"], "K12": ["k12"],
    "邀请": ["邀请", "自动拉", "拉入"], "母号": ["母号"], "子号": ["子号"],
    "成品号": ["成品号", "账号密码", "普号", "白号"], "代充": ["代充"],
    "直充": ["直充"], "卡密": ["卡密", "cdk", "兑换码"], "API": ["api", "apikey", "api key"],
    "自动发货": ["自动发货", "秒发"], "月付": ["月卡", "一个月", "1个月", "30天"],
}
RISK_RULES = {
    "无售后": ["无售后", "不售后", "售出不退"], "无质保": ["无质保", "不质保"],
    "仅首登保障": ["质保首登", "仅首登", "首登售后"], "账号密码交付": ["账号密码", "邮箱密码", "成品号"],
    "团队席位": ["团队邀请", "车位", "自动拉", "拉入团队"], "限制退款": ["买错不退", "不可退款", "售出不退"],
    "共享号池": SHARED_POOL_MARKERS, "中转服务": RELAY_MARKERS, "体验或日抛": TRIAL_MARKERS,
}
COMPARABLE_DELIVERY_TYPES = {
    "subscription_recharge", "finished_account", "semi_finished_account",
    "team_seat", "card_code", "api_credit",
}


@dataclass(slots=True)
class Classification:
    slug: str | None
    tags: list[str]
    risks: list[str]
    confidence: int
    delivery_type: str
    is_comparable: bool
    service_period: str
    warranty: str
    use_scenarios: list[str]
    item_fingerprint: str


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\s_\-—|/\\]+", " ", (text or "").casefold())).strip()


def contains(text: str, needles: list[str]) -> bool:
    return any(norm(needle) in text for needle in needles)


def pro_multiplier(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text).replace("×", "x").replace("✖", "x").replace("倍", "x").replace("\ufe0f", "")
    for multiplier in (20, 5):
        value = str(multiplier)
        if re.search(rf"pro.*?x?{value}x?(?!\d)|(?<!\d){value}x?.*?pro", compact):
            return multiplier
    return None


def delivery_form(text: str) -> str:
    account_markers = ["成品", "半成品", "账号", "首登", "已接码", "未接码", "账号密码", "独享"]
    if contains(text, CHATGPT_SERVICE_MARKERS) and not contains(text, account_markers):
        return "verification_service"
    if contains(text, SHARED_POOL_MARKERS):
        return "shared_pool"
    if contains(text, RELAY_MARKERS) and not contains(text, account_markers):
        return "relay_api"
    if contains(text, ["api额度", "api 额度", "api余额", "api 余额", "api key", "apikey", "token额度"]):
        return "api_credit"
    if contains(text, ["团队邀请", "team seat", "车位", "自动拉", "拉入团队", "子号"]):
        return "team_seat"
    if contains(text, TRIAL_MARKERS):
        return "trial_account"
    if contains(text, ["卡密", "cdk", "兑换码"]):
        return "card_code"
    if contains(text, ["半成品", "首登号", "未接码"]):
        return "semi_finished_account"
    if contains(text, ["成品", "账号密码", "邮箱密码", "已接码", "独享账号", "账号"]):
        return "finished_account"
    if contains(text, ["官方充值", "官方直充", "直充", "代充", "充值", "订阅"]):
        return "subscription_recharge"
    if contains(text, RELAY_MARKERS):
        return "relay_api"
    return "unknown"


def service_period(text: str) -> str:
    if contains(text, ["年卡", "一年", "1年", "12个月", "365天", "年付"]): return "one_year"
    if contains(text, ["六个月", "6个月", "半年", "半年卡"]): return "six_months"
    if contains(text, ["三个月", "3个月", "季度", "季卡"]): return "three_months"
    if contains(text, ["月卡", "一个月", "1个月", "30天", "月付"]): return "one_month"
    if contains(text, ["周卡", "一周", "1周", "7天"]): return "one_week"
    if contains(text, ["日抛", "一天", "1天", "24小时", "24h"]): return "one_day"
    return "unknown"


def warranty_type(text: str) -> str:
    if contains(text, ["无质保", "不质保"]): return "none"
    if contains(text, ["质保首登", "仅首登", "首登售后", "首登质保"]): return "first_login"
    if re.search(r"质保.{0,4}(1\s*小时|一\s*小时)|(?:1\s*小时|一\s*小时).{0,4}质保", text): return "one_hour"
    if re.search(r"质保.{0,4}(24\s*小时|1\s*天|一\s*天)|(?:24\s*小时|1\s*天|一\s*天).{0,4}质保", text): return "one_day"
    if re.search(r"质保.{0,4}(3\s*天|三\s*天)|(?:3\s*天|三\s*天).{0,4}质保", text): return "three_days"
    if re.search(r"质保.{0,4}(7\s*天|七\s*天)|(?:7\s*天|七\s*天).{0,4}质保", text): return "seven_days"
    if contains(text, ["全程质保", "订阅期质保", "质保到期"]): return "subscription_term"
    return "unknown"


def usage_scenarios(text: str) -> list[str]:
    rules = [
        ("web", ["网页", "web"]), ("desktop", ["客户端", "app", "桌面端"]),
        ("codex", ["codex"]), ("api", ["api", "apikey", "api key"]),
        ("relay", ["中转", "反代"]),
    ]
    return [label for label, markers in rules if contains(text, markers)]


def fingerprint_component(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value.casefold())
    value = re.sub(r"(?<!\d)\d{1,2}\s*[./-]\s*\d{1,2}(?!\d)", " ", value)
    value = re.sub(r"(?<!\d)\d{1,2}\s*点(?!\d)", " ", value)
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def item_fingerprint(title: str, description: str, slug: str | None, delivery_type: str, period: str, warranty: str) -> str:
    payload = "|".join([
        slug or "unclassified", fingerprint_component(title), fingerprint_component(description)[:2000],
        delivery_type, period, warranty,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chatgpt_tier(text: str) -> str | None:
    if contains(text, CHATGPT_K12_MARKERS):
        return "chatgpt-k12"
    multiplier = pro_multiplier(text)
    if multiplier == 20:
        return "chatgpt-pro-20x"
    if multiplier == 5:
        return "chatgpt-pro-5x"
    if contains(text, CHATGPT_PRO_MARKERS):
        return "chatgpt-pro"
    if contains(text, CHATGPT_PLUS_MARKERS):
        return "chatgpt-plus"
    return None


def explicit_brands(text: str) -> list[str]:
    return [name for name, markers in BRAND_MARKERS.items() if contains(text, markers)]


def first_title_brand(text: str) -> str | None:
    if contains(text, ["openai codex", "open ai codex"]):
        return "codex"
    positions: list[tuple[int, str]] = []
    for brand, markers in BRAND_MARKERS.items():
        for marker in markers:
            position = text.find(norm(marker))
            if position >= 0:
                positions.append((position, brand))
    return min(positions)[1] if positions else None


def compact_latin(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def platform_16688_chatgpt_alias_tier(value: str) -> str | None:
    compact = compact_latin(value)
    if any(marker in compact for marker in ("pro20x", "20xpro", "prox20", "x20pro")):
        return "chatgpt-pro-20x"
    if any(marker in compact for marker in ("pro5x", "5xpro", "prox5", "x5pro")):
        return "chatgpt-pro-5x"
    if any(marker in compact for marker in ("gptpro", "gtppro", "gpro")):
        return "chatgpt-pro"
    if any(marker in compact for marker in ("gptplus", "gtpplus", "gplus")):
        return "chatgpt-plus"
    if any(marker in compact for marker in ("gptgo", "gtpgo", "ggo")):
        return "chatgpt-go"
    return None


def platform_16688_grok_alias(value: str) -> str | None:
    compact = compact_latin(value)
    if any(marker in compact for marker in ("groheavy", "grosuper", "supergro")):
        return "grok-super"
    if "grofree" in compact:
        return "grok-account"
    return None


def classify_16688_alias(title_text: str, category_text: str, description_text: str) -> str | None:
    if (
        contains(title_text, CHATGPT_NON_PRODUCT_MARKERS)
        and not contains(title_text, CHATGPT_EXPLICIT_PRODUCT_MARKERS)
    ) or contains(title_text, NON_TARGET_PLUS_MARKERS):
        return None

    alias_identity = norm(" ".join([title_text, category_text]))
    if contains(alias_identity, NON_TARGET_PLUS_MARKERS) or contains(alias_identity, GENERIC_EMAIL_MARKERS):
        return None

    has_chatgpt_alias = platform_16688_chatgpt_alias_tier(alias_identity) is not None or contains(
        alias_identity,
        BRAND_MARKERS["chatgpt"],
    )
    if has_chatgpt_alias and contains(alias_identity, CHATGPT_API_MARKERS):
        if contains(alias_identity, ["中转", "倍率"]):
            return None
        return "openai-api-credit"

    title_grok = platform_16688_grok_alias(title_text)
    if title_grok:
        return title_grok
    title_alias = platform_16688_chatgpt_alias_tier(title_text)
    if title_alias:
        return title_alias

    title_plain_tier = None
    if contains(title_text, CHATGPT_PLUS_MARKERS):
        title_plain_tier = "chatgpt-plus"
    elif contains(title_text, CHATGPT_GO_MARKERS):
        title_plain_tier = "chatgpt-go"
    elif contains(title_text, CHATGPT_PRO_MARKERS):
        title_plain_tier = "chatgpt-pro"

    context = " ".join([category_text, description_text])
    context_grok = platform_16688_grok_alias(context)
    context_chatgpt = platform_16688_chatgpt_alias_tier(context)
    if title_plain_tier and context_chatgpt:
        return title_plain_tier
    if context_grok and not context_chatgpt and contains(title_text, CATEGORY_COMMERCE_MARKERS):
        return context_grok
    if context_chatgpt and contains(title_text, CATEGORY_COMMERCE_MARKERS):
        return context_chatgpt
    return None


def classify_identity(
    title_text: str,
    category_text: str,
    description_text: str = "",
    source_platform: str = "",
) -> tuple[str | None, bool]:
    identity_text = norm(" ".join([title_text, category_text]))
    tier_text = norm(" ".join([identity_text, description_text]))
    if contains(identity_text, RELAY_MARKERS) and contains(identity_text, ["api", "key", "token", "额度"]):
        return None, False
    brand = first_title_brand(title_text)
    if brand is None:
        if "plus" in title_text and contains(title_text, IMPLICIT_CHATGPT_MARKERS) and not contains(title_text, NON_TARGET_PLUS_MARKERS):
            brand = "chatgpt"
    if brand is None:
        category_brands = explicit_brands(category_text)
        if len(category_brands) > 1:
            return None, False
        if len(category_brands) == 1 and not contains(title_text, GENERIC_EMAIL_MARKERS) and contains(title_text, CATEGORY_COMMERCE_MARKERS):
            brand = category_brands[0]
    if brand is None:
        if str(source_platform or "").strip().casefold() == PLATFORM_16688:
            alias_slug = classify_16688_alias(title_text, category_text, description_text)
            if alias_slug:
                return alias_slug, True
        return None, False
    if brand == "codex":
        return "codex-access", True
    if brand == "claude":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "claude-api-access", True
        if contains(identity_text, ["claude pro", "claude会员", "claude 会员"]):
            return "claude-pro", True
        return "claude-account", False
    if brand == "gemini":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "gemini-api-access", True
        if contains(identity_text, ["gemini advanced", "gemini pro会员", "google one ai"]):
            return "gemini-advanced", True
        return "gemini-account", False
    if brand == "grok":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "grok-api-access", True
        if contains(identity_text, ["supergrok", "super grok", "grok super"]):
            return "grok-super", True
        return "grok-account", False
    if brand == "x":
        if contains(identity_text, ["premium business", "premium organization", "premium organisation", "企业认证", "金标", "灰标"]):
            return None, False
        if contains(identity_text, ["premium+", "premium +", "premium plus", "premiumplus"]):
            return "x-premium-plus", True
        if contains(identity_text, ["basic", "基础版"]):
            return "x-premium-basic", True
        if contains(identity_text, ["premium", "twitter blue", "推特会员", "蓝v", "蓝标"]):
            return "x-premium", True
        return None, False
    if contains(identity_text, CHATGPT_API_MARKERS):
        if contains(identity_text, ["中转", "倍率"]):
            return None, False
        return "openai-api-credit", True
    if (
        contains(title_text, CHATGPT_NON_PRODUCT_MARKERS)
        and not contains(title_text, CHATGPT_EXPLICIT_PRODUCT_MARKERS)
    ):
        return None, False
    if (contains(title_text, CHATGPT_SERVICE_MARKERS) and not contains(title_text, CHATGPT_PRODUCT_MARKERS)) or (
        contains(title_text, GENERIC_EMAIL_MARKERS) and not contains(title_text, CHATGPT_PRODUCT_MARKERS)
    ):
        return "chatgpt-access-service", True
    if contains(title_text, CHATGPT_FREE_MARKERS):
        return "chatgpt-account", True
    if contains(title_text, CHATGPT_GO_MARKERS):
        return "chatgpt-go", True
    title_tier = chatgpt_tier(title_text)
    if title_tier:
        return title_tier, True
    refined_tier = chatgpt_tier(tier_text)
    if refined_tier and refined_tier != "chatgpt-plus":
        return refined_tier, True
    if contains(title_text, CHATGPT_AMBIGUOUS_CREDIT_MARKERS):
        return None, False
    if contains(title_text, CHATGPT_PRODUCT_MARKERS):
        return "chatgpt-account", False
    return None, False


def classify(
    title: str,
    category: str = "",
    raw: dict[str, Any] | None = None,
    *,
    source_platform: str = "",
) -> Classification:
    raw = raw or {}
    source_platform = source_platform or str(raw.get("source_platform") or "")
    description_values = [raw.get("description", "")]
    category_values = [category]
    if source_platform.strip().casefold() == PLATFORM_16688:
        description_values.extend(raw.get(key, "") for key in ("content", "instruction", "remark"))
        category_value = raw.get("sourceCategory") or raw.get("source_category")
        if isinstance(category_value, dict):
            category_values.append(category_value.get("name", ""))
        elif category_value:
            category_values.append(str(category_value))
    category_text = norm(" ".join(str(value or "") for value in category_values))
    description_text = norm(" ".join(str(value or "") for value in description_values))
    detail_text = norm(" ".join([title, category_text, description_text]))
    slug, specific_match = classify_identity(norm(title), category_text, description_text, source_platform)
    tags = [label for label, words in TAG_RULES.items() if any(norm(x) in detail_text for x in words)]
    risks = [label for label, words in RISK_RULES.items() if any(norm(x) in detail_text for x in words)]
    if slug != "chatgpt-k12":
        tags = [tag for tag in tags if tag not in {"Team", "Business", "K12", "邀请", "母号", "子号"}]
    delivery_type = delivery_form(norm(title))
    if delivery_type == "unknown":
        delivery_type = delivery_form(detail_text)
    period = service_period(norm(title))
    if period == "unknown":
        described_period = service_period(detail_text)
        if described_period not in {"one_day", "one_week"}:
            period = described_period
    warranty = warranty_type(norm(title))
    if warranty == "unknown":
        warranty = warranty_type(detail_text)
    return Classification(
        slug=slug,
        tags=tags,
        risks=risks,
        confidence=88 if specific_match else 68 if slug else 0,
        delivery_type=delivery_type,
        is_comparable=delivery_type in COMPARABLE_DELIVERY_TYPES,
        service_period=period,
        warranty=warranty,
        use_scenarios=usage_scenarios(detail_text),
        item_fingerprint=item_fingerprint(title, description_text, slug, delivery_type, period, warranty),
    )


def parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        return utcnow()


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_json(value: Any, default: Any):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def stock_status(value: str, count: int | None) -> str:
    text = norm(value)
    if any(x in text for x in ["有货", "in stock", "low stock", "unlimited"]): return "in_stock"
    if any(x in text for x in ["缺货", "售罄", "out of stock"]): return "out_of_stock"
    if any(x in text for x in ["下架", "不可用", "暂停", "关闭", "unavailable", "not purchasable"]): return "unavailable"
    if count is not None: return "in_stock" if count > 0 else "out_of_stock"
    return "unknown"


def ensure_products(db: Session) -> dict[str, Product]:
    definitions = [
        ("chatgpt-account", "OpenAI", "ChatGPT Free", "Free 普号与基础账号", "account", "聚合公开售卖的 ChatGPT Free 普号和基础账号。"),
        ("chatgpt-plus", "OpenAI", "ChatGPT Plus", "Plus 订阅、代充与成品号", "subscription", "聚合 ChatGPT Plus 的代充、直充、月付与成品号报价。"),
        ("chatgpt-go", "OpenAI", "ChatGPT Go", "Go 订阅、充值与成品号", "subscription", "聚合标题明确标注为 ChatGPT Go 的订阅、充值与成品号公开报价。"),
        ("chatgpt-k12", "OpenAI", "ChatGPT K12", "Team / Business、团队邀请与 K12", "subscription", "聚合 ChatGPT Team、Business、K12、团队邀请、车位和自动拉等公开报价。"),
        ("chatgpt-pro-5x", "OpenAI", "ChatGPT Pro 5x", "Pro 5x 订阅与成品号", "subscription", "聚合明确标注为 ChatGPT Pro 5x 的公开报价。"),
        ("chatgpt-pro-20x", "OpenAI", "ChatGPT Pro 20x", "Pro 20x 订阅与成品号", "subscription", "聚合明确标注为 ChatGPT Pro 20x 的公开报价。"),
        ("chatgpt-pro", "OpenAI", "ChatGPT Pro", "未注明 5x 或 20x 的 Pro", "subscription", "聚合未明确标注 5x 或 20x 倍率的 ChatGPT Pro 公开报价。"),
        ("openai-api-credit", "OpenAI", "OpenAI API 额度", "API Key 与额度商品", "api", "聚合 OpenAI API 额度、余额和 Key 类商品。"),
        ("chatgpt-access-service", "OpenAI", "ChatGPT / Codex 周边服务", "接码、验证与开通辅助商品", "service", "聚合明确用于 ChatGPT 或 Codex 的接码、验证与开通辅助商品。"),
        ("codex-access", "OpenAI", "Codex 账号与访问", "账号、订阅与访问类商品", "account", "聚合 Codex 账号、订阅和访问类公开报价。"),
        ("claude-pro", "Claude", "Claude Pro", "个人会员订阅", "subscription", "聚合 Claude Pro 公开报价。"),
        ("claude-account", "Claude", "Claude 账号", "基础账号与访问类商品", "account", "聚合 Claude 基础账号与访问类公开报价。"),
        ("claude-api-access", "Claude", "Claude API", "API Key、Token 与额度商品", "api", "聚合 Claude API Key、Token 与额度类公开报价。"),
        ("gemini-advanced", "Gemini", "Gemini Advanced", "Google One AI 会员", "subscription", "聚合 Gemini Advanced 与 Google One AI 报价。"),
        ("gemini-account", "Gemini", "Gemini 账号", "基础账号与访问类商品", "account", "聚合 Gemini 基础账号与访问类公开报价。"),
        ("gemini-api-access", "Gemini", "Gemini API", "API Key、Token 与额度商品", "api", "聚合 Gemini API Key、Token 与额度类公开报价。"),
        ("grok-super", "Grok", "SuperGrok", "SuperGrok 订阅与代充", "subscription", "聚合 SuperGrok 订阅与代充公开报价。"),
        ("grok-account", "Grok", "Grok 账号", "基础账号与访问类商品", "account", "聚合 Grok 基础账号与访问类公开报价。"),
        ("grok-api-access", "Grok", "Grok API", "API Key、Token 与额度商品", "api", "聚合 Grok API Key、Token 与额度类公开报价。"),
        ("x-premium-basic", "X", "X Premium Basic", "Basic 订阅与充值", "subscription", "聚合 X Premium Basic 订阅与充值公开报价。"),
        ("x-premium", "X", "X Premium", "Premium 订阅与充值", "subscription", "聚合 X Premium 订阅与充值公开报价。"),
        ("x-premium-plus", "X", "X Premium+", "Premium+ 订阅与充值", "subscription", "聚合 X Premium+ 订阅与充值公开报价。"),
    ]
    existing = {x.slug: x for x in db.scalars(select(Product))}
    for slug, platform, name, subtitle, product_type, description in definitions:
        item = existing.get(slug)
        if item is None:
            item = Product(slug=slug)
            db.add(item)
            existing[slug] = item
        item.platform = platform
        item.display_name = name
        item.subtitle = subtitle
        item.description = description
        item.product_type = product_type
        item.search_keywords = [name, platform, product_type]
    legacy_team = existing.get("chatgpt-team-business")
    if legacy_team is not None:
        legacy_team.is_visible = False
    db.flush()
    return existing


def session_for(url: str):
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def begin_snapshot(db: Session, source: str) -> CatalogSnapshot:
    snapshot = CatalogSnapshot(source=source)
    db.add(snapshot)
    db.flush()
    return snapshot


def upsert_offer(
    db: Session,
    record: dict[str, Any],
    products: dict[str, Product],
    snapshot_id: int | None = None,
    *,
    collected_offer_ids: set[int] | None = None,
) -> tuple[bool, bool]:
    token = str(record.get("token") or "").strip()
    if not token:
        raise ValueError("missing shop token")
    shop = db.scalar(select(Shop).where(Shop.token == token))
    observed_at = parse_dt(record.get("observed_at") or record.get("collected_at") or record.get("scanned_at"))
    if shop is None:
        shop = Shop(token=token, name=str(record.get("shop_name") or token), source_url=str(record.get("shop_url") or ""), platform=str(record.get("source_platform") or "ldxp"))
        db.add(shop); db.flush()
    shop.name = str(record.get("shop_name") or shop.name or token)
    shop.source_url = str(record.get("shop_url") or shop.source_url)
    shop.platform = str(record.get("source_platform") or shop.platform or "unknown")
    shop.source_score = int(record.get("source_score") or shop.source_score or 0)
    shop.status = str(record.get("shop_status") or "success")
    shop.consecutive_failures = int(record.get("consecutive_failures") or 0)
    shop.last_seen_at = observed_at
    shop.last_success_at = parse_dt(record.get("last_success_at")) if record.get("last_success_at") else observed_at

    key = str(record.get("product_key") or record.get("source_product_key") or record.get("product_url") or record.get("product_name") or "")[:300]
    raw = db.scalar(select(RawProduct).where(RawProduct.shop_id == shop.id, RawProduct.source_product_key == key))
    created = raw is None
    raw_json = parse_json(record.get("raw_json"), {})
    if raw is None:
        raw = RawProduct(shop_id=shop.id, source_product_key=key, original_name=str(record.get("product_name") or ""), first_seen_at=observed_at)
        db.add(raw); db.flush()
    raw.original_name = str(record.get("product_name") or raw.original_name)
    raw.original_category = str(record.get("category_name") or "")
    raw.source_url = str(record.get("product_url") or "")
    raw.raw_json = raw_json
    raw.last_seen_at = observed_at

    result = classify(
        raw.original_name,
        raw.original_category,
        raw_json,
        source_platform=str(record.get("source_platform") or shop.platform or ""),
    )
    offer = db.scalar(select(Offer).where(Offer.raw_product_id == raw.id))
    price = parse_decimal(record.get("listed_price") if record.get("listed_price") not in (None, "") else record.get("price"))
    currency = normalize_currency(record.get("currency"))
    count_raw = record.get("stock_count")
    try: count = int(float(count_raw)) if count_raw not in (None, "") else None
    except (TypeError, ValueError): count = None
    status = stock_status(str(record.get("product_status") or record.get("stock_status") or ""), count)
    changed = False
    is_new_offer = offer is None
    if offer is None:
        offer = Offer(raw_product_id=raw.id, shop_id=shop.id)
        db.add(offer); db.flush()
        changed = True
    elif offer.price != price or offer.currency != currency or offer.stock_count != count or offer.stock_status != status:
        changed = True
    offer.product_id = products[result.slug].id if result.slug and result.slug in products else None
    offer.price = price
    offer.currency = currency
    offer.stock_count = count
    offer.stock_status = status
    raw_delivery = record.get("auto_delivery")
    if isinstance(raw_delivery, bool):
        offer.auto_delivery = raw_delivery
    else:
        delivery = str(raw_delivery or "").strip().casefold()
        offer.auto_delivery = True if delivery in {"是", "true", "1"} else False if delivery in {"否", "false", "0"} else None
    offer.tags = result.tags
    offer.risk_flags = result.risks
    offer.classification_confidence = result.confidence
    offer.delivery_type = result.delivery_type
    offer.is_comparable = result.is_comparable
    offer.service_period = result.service_period
    offer.warranty = result.warranty
    offer.use_scenarios = result.use_scenarios
    offer.item_fingerprint = result.item_fingerprint
    if snapshot_id is not None:
        offer.snapshot_id = snapshot_id
    offer.source_url = raw.source_url
    offer.observed_at = observed_at
    if is_new_offer:
        offer.active = True
        offer.approved = result.slug is not None and result.confidence >= 80
    offer.updated_at = utcnow()
    if changed:
        db.add(OfferHistory(offer_id=offer.id, price=price, currency=currency, stock_count=count, stock_status=status, observed_at=observed_at))
    if collected_offer_ids is not None:
        collected_offer_ids.add(offer.id)
    return created, changed
