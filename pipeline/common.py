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
    "chatgpt": [
        "chatgpt", "chat gpt", "openai", "open ai", "gpt", "chat plus", "codex",
        "g free", "g-free", "gfree",
        "g-p-t", "g-pt", "g-p·t", "g·p·t", "chat g", "chatg"
    ],
    "claude": ["claude"],
    "gemini": ["gemini", "google one ai"],
    "grok": ["supergrok", "super grok", "grok", "x.ai", "x ai", "xai"],
    "x": ["x premium", "xpremium", "twitter", "推特"],
}
CHATGPT_API_MARKERS = ["openai api", "open ai api", "gpt api", "api额度", "api 额度", "api余额", "api 余额", "api key", "apikey"]
CHATGPT_K12_MARKERS = ["chatgpt team", "gpt team", "business", "k12", "团队", "车位", "母号", "自动拉", "团队邀请"]
CHATGPT_PRO_MARKERS = ["chatgpt pro", "gpt pro", "200刀"]
CHATGPT_PLUS_MARKERS = [
    "chatgpt plus", "gpt plus", "chat plus", "plus", "puls", "plsu",
    "codex plus", "codexplus", "codex plus账号", "codexplus账号", "codex 账号", "codex账号", "codex成品", "codex 成品"
]
CHATGPT_GO_MARKERS = ["chatgpt go", "gpt go", "go会员", "go订阅", "codex go", "go菲区", "go cdk"]
CHATGPT_FREE_MARKERS = [
    "chatgpt free", "gpt free", "g free", "g-free", "gfree",
    "codex free", "codex-free", "codexfree", "codex【free", "codex 【free",
    "free账号", "free号", "free 账号", "free 号", "免费账号", "普通账号", "普通号", "普号", "白号",
    "free账密", "free-账密", "free 账密", "free成品", "free 成品", "free底号", "free 底号",
    "outlook free", "icloud free", "gmail free", "yahoo free",
    "福利号", "资格号", "体验号",
    "可升级plus", "可升plus", "升级plus", "可开plus", "开plus专用", "开通plus专用", "开通plus必备", "升级专用", "plus底号", "好底号", "未绑卡",
    "不含plus", "不含 plus", "不是plus", "不是 plus", "非plus", "非 plus", "无plus", "无 plus"
]
CHATGPT_NON_PRODUCT_MARKERS = ["镜像站", "教程", "使用指南", "购买指南", "攻略", "授权神器", "自动化授权"]
CHATGPT_AMBIGUOUS_CREDIT_MARKERS = ["刀额度", "美元额度"]
IMPLICIT_CHATGPT_MARKERS = ["成品", "半成品", "首登"]
NON_TARGET_PLUS_MARKERS = ["百度", "网盘", "小红书", "加速器", "梯子", "夸克", "迅雷", "youtube", "netflix", "spotify", "office", "wps"]
PLATFORM_16688 = "16688"
RELAY_MARKERS = ["中转", "反代", "sub2api", "倍率", "分组"]
SHARED_POOL_MARKERS = ["号池", "共享池", "共享号", "拼车池", "拼车", "共享账号", "多人共享", "车位", "车号"]
TRIAL_MARKERS = ["日抛", "体验版", "体验号", "试用号", "小时号"]
GENERIC_EMAIL_MARKERS = ["gmail", "谷歌邮箱", "谷歌邮件", "谷歌账号", "outlook", "hotmail", "icloud", "ic邮箱", "微软邮箱"]
CATEGORY_COMMERCE_MARKERS = [
    "plus", "pro", "team", "business", "max", "advanced", "ultra", "super", "heavy",
    "会员", "订阅", "代充", "直充", "充值", "接码", "接马", "实卡号码", "实卡", "号码",
    "提链", "提炼", "支付链接", "底号", "api", "key", "token", "额度", "成品", "账号", "首登"
]
CHATGPT_SERVICE_MARKERS = [
    "代接码", "代接马", "手机接码", "实卡接码", "一次性接码", "接码服务", "接码卡密", "纯接码", "接马服务",
    "短信代接", "代接短信", "接验证码", "短信验证", "手机验证", "提链", "扫码对接", "二维码生成",
    "cyber认证", "persona认证",
    "提炼", "代提链", "直卡支付链接", "支付链接", "卡头开通plus必备", "开通plus必备", "提炼cdk",
    "实卡号码", "无限接马", "无限接码", "一次性接马"
]
CHATGPT_PRODUCT_MARKERS = [
    "成品", "半成品", "账号", "已注册", "会员", "订阅", "代充", "直充", "充值", "白号", "普号",
    "邮箱直登", "重置号", "反代", "已接码", "已接马", "已接🐎",
    "未接码", "未接马", "未接🐎", "免接码", "免接马", "账密", "发货格式", "直登", "原生支付",
    "独享", "自用", "直卡", "新号", "首登"
]
CHATGPT_EXPLICIT_PRODUCT_MARKERS = [
    "成品", "半成品", "账号", "已注册", "会员", "充值", "代充", "直充", "卡密", "cdk", "兑换码",
    "重置号", "已接码", "已接马", "已接🐎", "未接码", "未接马"
]


def is_chatgpt_service(text: str) -> bool:
    if contains(text, CHATGPT_SERVICE_MARKERS):
        return True
    if "接码" in text or "接马" in text or "接🐎" in text:
        without_status = (
            text.replace("已接码", "")
            .replace("已接马", "")
            .replace("已接🐎", "")
            .replace("未接码", "")
            .replace("未接马", "")
            .replace("未接🐎", "")
            .replace("免接码", "")
            .replace("免接马", "")
            .replace("需自行接码", "")
            .replace("需自行接马", "")
            .replace("自行接码", "")
            .replace("自行接马", "")
            .replace("不接码", "")
            .replace("不接马", "")
        )
        if "接码" in without_status or "接马" in without_status or "接🐎" in without_status:
            return True
    return False


TAG_RULES = {
    "Team": ["team", "团队", "车位"], "Business": ["business"], "K12": ["k12"],
    "邀请": ["邀请", "自动拉", "拉入"], "母号": ["母号"], "子号": ["子号"],
    "成品号": ["成品号", "账号密码", "普号", "白号"],
    "已接码": ["已接码", "已接马", "已接🐎", "已绑手机", "已绑定手机"],
    "带RT": ["带rt", "含rt", "有rt", "带 rt"],
    "Sub2API": ["sub2api", "sub2", "cpa格式", "cpa"],
    "Codex": ["codex"],
    "代充": ["代充"],
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
    "session_token", "team_seat", "card_code", "api_credit",
    "verification_service",
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
    return re.sub(r"\s+", " ", re.sub(r"[\s_\-—|/\\]+", " ", (str(text or "")).casefold())).strip()


def contains(text: str, needles: list[str]) -> bool:
    target = norm(text)
    return any(norm(needle) in target for needle in needles)


def strip_exclusions(text: str) -> str:
    return re.sub(r"(?:除|不可|不支持|排除|不含|非|无)\s*(?:codex|plus|puls|plsu)", "", text, flags=re.IGNORECASE)


TUTORIAL_ATTACHMENT_RE = re.compile(
    r"(?:附|带|内附|附带|赠|送|含|带有|包括|配合|看|参考)\s*(?:完整|详细|图文|保姆|小白|登录|使用|中文|操作|激活|配置|新手)?\s*(?:视频|图文)?\s*(?:教程|指南|方法)"
)

TUTORIAL_STANDALONE_MARKERS = [
    "保姆教程", "保姆级教程", "图文教程", "文字教程", "视频教程", "使用指南", "购买指南",
    "注册教程", "开通教程", "订阅教程", "修改教程", "搭建教程", "配置教程", "破甲教程",
    "接马教程", "接码教程", "手把手", "使用教程", "操作教程", "激活教程", "使用方法",
    "教程持续更新", "指南教程", "完整教程", "详细教程", "焚诀教程", "手搓"
]


def is_non_product(title_text: str, category_text: str = "", description_text: str = "") -> bool:
    t_l = norm(title_text)
    c_l = norm(category_text)
    d_l = norm(description_text)

    if any(m in c_l for m in ["教程", "虚拟卡", "0刀卡和一刀卡", "反代教程"]):
        return True
    if any(m in d_l for m in ["【测试商品】", "仅图文教程", "本商品为教程", "不会发货，不要购买"]):
        return True

    if t_l.startswith("【教程】") or t_l.startswith("[教程]") or t_l.startswith("教程"):
        return True

    if any(k in t_l for k in ["教程", "指南", "攻略"]):
        t_without_attachment = TUTORIAL_ATTACHMENT_RE.sub(" ", t_l)
        if any(m in t_without_attachment for m in TUTORIAL_STANDALONE_MARKERS):
            return True
        if re.search(r"(?:教程|指南|攻略)\s*(?:[！!。.\-_【】\[\]()（）]|\b|$)", t_without_attachment):
            return True

    direct_title_rejects = [
        "不要拍", "不要购买", "不可拍", "测试商品", "测试号", "非商品", "买了不发", "防失联", "补差价", "专拍",
        "接码渠道", "接码平台", "接码地址", "手把手",
        "邀请返利", "推广返利", "邀请推广", "邀请额度", "额度增加", "邀请资格",
        "虚拟卡", "0刀卡", "一刀卡",
        "优惠链接", "提取链接",
    ]
    if any(m in t_l for m in direct_title_rejects):
        return True
    return False


def pro_multiplier(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text).replace("×", "x").replace("✖", "x").replace("倍", "x").replace("\ufe0f", "")
    for multiplier in (20, 5):
        value = str(multiplier)
        if re.search(rf"pro.*?x?{value}x?(?!\d)|(?<!\d){value}x?.*?pro", compact):
            return multiplier
    return None


def delivery_form(text: str) -> str:
    account_markers = [
        "成品", "半成品", "账号", "首登", "已接码", "已接马", "已接🐎", "未接码", "未接马", "未接🐎", "免接码", "免接马",
        "账号密码", "独享", "重置号", "邮箱直登", "原生支付", "gmail", "outlook", "icloud", "自用", "质保首登", "直卡", "新号"
    ]
    if contains(text, ["只能反代", "无账号和密码", "无账号密码", "没有账号密码", "没有邮箱账密", "只可反代", "反代专用", "json发货", "仅支持反代", "仅反代"]):
        return "session_token"
    if contains(text, ["团队邀请", "team seat", "自动拉", "拉入团队", "子号", "team"]):
        return "team_seat"
    if any(w in text for w in ["拼车", "共享账号", "多人共享", "号池", "共享池", "共享号", "拼车池"]):
        return "shared_pool"
    if contains(text, SHARED_POOL_MARKERS):
        return "shared_pool"
    if is_chatgpt_service(text) and not contains(text, ["成品", "账号密码", "账密", "发货格式", "邮箱直登", "无账号密码", "反代", "重置号"]):
        return "verification_service"
    if contains(text, RELAY_MARKERS) and not contains(text, account_markers):
        return "relay_api"
    if contains(text, ["api额度", "api 额度", "api余额", "api 余额", "api key", "apikey", "token额度"]):
        return "api_credit"
    if contains(text, TRIAL_MARKERS):
        return "trial_account"
    if contains(text, ["官方充值", "官方直充", "直充", "代充", "充值", "订阅", "卡充"]):
        return "subscription_recharge"
    if contains(text, ["卡密", "cdk", "兑换码"]):
        return "card_code"
    if contains(text, ["半成品", "首登号", "未接码", "未接马", "需自行接马", "需自行接码"]):
        return "semi_finished_account"
    if contains(text, ["成品", "账号密码", "邮箱密码", "已接码", "已接马", "已接🐎", "独享账号", "账号", "重置号", "邮箱直登", "原生支付", "独享", "自用", "gmail", "outlook", "icloud", "保首登", "质保首登"]):
        return "finished_account"
    if contains(text, RELAY_MARKERS):
        return "relay_api"
    return "unknown"


def service_period(text: str) -> str:
    if contains(text, ["年卡", "一年", "1年", "12个月", "365天", "年付"]): return "one_year"
    if contains(text, ["六个月", "6个月", "半年", "半年卡"]): return "six_months"
    if contains(text, ["三个月", "3个月", "季度", "季卡"]): return "three_months"
    if contains(text, ["月卡", "一个月", "1个月", "30天", "月付"]) or re.search(r"(?:2[0-9]|3[0-1])\s*天", text): return "one_month"
    if contains(text, ["周卡", "一周", "1周", "7天"]): return "one_week"
    if contains(text, ["日抛", "一天", "1天", "24小时", "24h"]): return "one_day"
    return "unknown"


def warranty_type(text: str) -> str:
    if contains(text, ["无质保", "不质保"]): return "none"
    if contains(text, ["质保首登", "仅首登", "首登售后", "首登质保"]): return "first_login"
    if re.search(r"质保.{0,4}(?:2[0-9]|3[0-1])\s*天|(?:2[0-9]|3[0-1])\s*天.{0,4}质保|质保.{0,4}(?:月|30天)|(?:月|30天).{0,4}质保", text): return "subscription_term"
    if re.search(r"质保.{0,4}(1\s*小时|一\s*小时)|(?:1\s*小时|一\s*小时).{0,4}质保", text): return "one_hour"
    if re.search(r"质保.{0,4}(24\s*小时|1\s*天|一\s*天)|(?:24\s*小时|1\s*天|一\s*天).{0,4}质保", text): return "one_day"
    if re.search(r"质保.{0,4}(3\s*天|三\s*天)|(?:3\s*天|三\s*天).{0,4}质保", text): return "three_days"
    if re.search(r"质保.{0,4}(7\s*天|七\s*天)|(?:7\s*天|七\s*天).{0,4}质保", text): return "seven_days"
    if contains(text, ["全程质保", "订阅期质保", "质保到期"]): return "subscription_term"
    return "unknown"


def usage_scenarios(text: str) -> list[str]:
    rules = [
        ("web", ["网页", "web"]), ("desktop", ["客户端", "app", "桌面端"]),
        ("codex", ["codex", "sub2api", "sub2", "cpa", "带rt"]), ("api", ["api", "apikey", "api key"]),
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
    if contains(text, ["(cx", "中转站", "不限时"]):
        return None
    if "plus分组" in text or "api分组" in text or "中转分组" in text:
        return None

    # Free accounts or upgrade helper底号 or link tools must not be classified into Plus/Pro
    if contains(text, CHATGPT_FREE_MARKERS) or contains(text, [
        "可升级", "开plus专用", "开通plus专用", "开通plus必备", "提链", "提炼", "支付链接", "直卡支付链接",
        "自行开通plus", "开通plus"
    ]):
        return None

    if any(re.search(rf"(?<!\d){q}\s*(?:刀|美金|\$)(?!\d)", text) for q in [5, 10, 15, 25, 30, 50, 100, 120, 150, 200, 300, 500, 1000]):
        if any(w in text for w in ["额度", "余额", "api", "key", "token", "sol", "image"]):
            return None

    if contains(text, CHATGPT_K12_MARKERS) or any(w in text for w in ["team", "周额", "周限额", "子号", "母号", "团队邀请"]):
        if any(w in text for w in ["k12", "edu", "教育", "学生", "高校"]):
            return "chatgpt-k12"
        return "chatgpt-k12"

    multiplier = pro_multiplier(text)
    if multiplier in (5, 20):
        if any(w in text for w in ["额度", "美金", "team", "子号", "中转", "号池", "api"]):
            return None
        return "chatgpt-pro-20x" if multiplier == 20 else "chatgpt-pro-5x"

    if contains(text, ["chatgpt pro", "gpt pro", "chatgpt-pro", "gpt-pro"]):
        if any(w in text for w in ["team", "周额", "周限额", "子号", "额度", "美金", "号池", "中转", "api"]):
            return None
        return "chatgpt-pro"
    if "200刀" in text and not any(w in text for w in ["team", "周额", "周限额", "子号", "额度", "美金", "号池", "中转", "api"]):
        return "chatgpt-pro"

    if contains(text, CHATGPT_PLUS_MARKERS):
        if any(w in text for w in ["team", "周额", "周限额", "子号", "额度", "中转"]):
            return None
        if re.search(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|10|15|25|30|50|100|200|300|500|1000)\s*[刀$]", text):
            if not re.search(r"(?<!\d)20\s*[刀$]", text):
                return None
        if re.search(r"\bapi\b", text, re.IGNORECASE) and not contains(text, ["代充", "直充", "充值", "月卡", "30天", "成品", "sub2"]):
            return None
        return "chatgpt-plus"

    return None


def explicit_brands(text: str) -> list[str]:
    return [name for name, markers in BRAND_MARKERS.items() if contains(text, markers)]


def first_title_brand(text: str) -> str | None:
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
    clean_title = strip_exclusions(title_text)
    clean_category = strip_exclusions(category_text)
    clean_identity = f"{clean_title} {clean_category}"
    identity_text = norm(" ".join([title_text, category_text]))
    tier_text = norm(" ".join([identity_text, description_text]))

    if is_non_product(title_text, category_text, description_text):
        return None, False

    if contains(identity_text, ["(cx", "中转站"]):
        return None, False
    if contains(title_text, ["分组"]) or contains(category_text, ["plus分组", "api分组", "中转分组", "token分组"]):
        return None, False
    if contains(identity_text, RELAY_MARKERS) and contains(identity_text, ["api", "key", "token", "额度"]):
        return None, False

    brand = first_title_brand(clean_title)
    if brand is None:
        if "plus" in clean_title and contains(clean_title, IMPLICIT_CHATGPT_MARKERS) and not contains(clean_title, NON_TARGET_PLUS_MARKERS):
            brand = "chatgpt"
    if brand is None:
        if contains(clean_title, ["plus", "puls", "plsu", "team", "k12"]) and contains(clean_title, [
            "成品", "半成品", "账号", "已接码", "已接马", "已接🐎", "未接码", "未接马", "会员", "直充", "代充",
            "月卡", "反代", "json", "rt", "首登", "周限额", "团队邀请",
            "提链", "提炼", "支付链接", "开通plus", "底号", "可升级"
        ]):
            if not any(other in clean_title for other in ["google", "gemini", "claude", "twitter", "baidu", "百度", "microsoft"]):
                brand = "chatgpt"
    if brand is None:
        category_brands = explicit_brands(clean_category)
        if len(category_brands) > 1:
            return None, False
        if len(category_brands) == 1 and not contains(clean_title, GENERIC_EMAIL_MARKERS) and contains(clean_title, CATEGORY_COMMERCE_MARKERS):
            brand = category_brands[0]
    if brand is None and description_text:
        desc_norm = norm(description_text)
        if any(m in desc_norm for m in ["chatgpt plus", "chatgpt pro", "gpt-plus", "gpt plus", "gpt-pro", "gpt pro", "openai plus"]):
            brand = "chatgpt"
        elif any(m in desc_norm for m in ["claude pro", "claude-pro", "claude 会员", "claude 个人账号"]):
            brand = "claude"
        elif any(m in desc_norm for m in ["gemini advanced", "google one ai", "gemini pro会员"]):
            brand = "gemini"
        elif any(m in desc_norm for m in ["super grok", "supergrok", "grok super"]):
            brand = "grok"
        elif any(m in desc_norm for m in ["x premium", "twitter blue", "推特会员"]):
            brand = "x"
        elif any(m in desc_norm for m in ["codex", "cc switch", "codex++"]):
            brand = "codex"
    if brand is None:
        if str(source_platform or "").strip().casefold() == PLATFORM_16688:
            alias_slug = classify_16688_alias(title_text, category_text, description_text)
            if alias_slug:
                return alias_slug, True
        return None, False

    is_sub2api_only = any(w in tier_text for w in [
        "只能反代", "仅支持反代", "无账号和密码", "无账号密码", "没有账号密码",
        "没有邮箱账密", "只可反代", "反代专用", "没有账密"
    ])

    if brand == "claude":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "claude-api-access", True
        if contains(identity_text, ["claude pro", "claude会员", "claude 会员"]) or contains(tier_text, ["claude pro"]):
            return "claude-pro", True
        return "claude-account", False
    if brand == "gemini":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "gemini-api-access", True
        if contains(identity_text, ["gemini advanced", "gemini pro会员", "google one ai"]) or contains(tier_text, ["gemini advanced"]):
            return "gemini-advanced", True
        return "gemini-account", False
    if brand == "grok":
        if contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "grok-api-access", True
        if contains(tier_text, ["中转站", "周限", "速刷"]):
            return None, False
        if contains(identity_text, ["supergrok", "super grok", "grok super", "groksuper"]) or contains(tier_text, ["supergrok", "super grok", "grok super", "groksuper"]):
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

    is_service = (
        is_chatgpt_service(title_text)
        or is_chatgpt_service(category_text)
        or contains(title_text, ["提链", "提炼", "支付链接", "实卡号码", "无限接马", "卡头开通plus必备"])
        or contains(category_text, ["提链", "提炼", "接码", "接马"])
    )
    if is_service and not contains(title_text, ["成品号", "独享成品", "独享账号"]):
        return "chatgpt-access-service", True

    if contains(title_text, CHATGPT_GO_MARKERS):
        return "chatgpt-go", True

    title_tier = chatgpt_tier(clean_title)
    if title_tier:
        return title_tier, True

    is_free = (
        contains(title_text, CHATGPT_FREE_MARKERS)
        or contains(category_text, ["g free", "codex free", "free", "普号", "白号", "福利号"])
        or contains(clean_title, ["可升级plus", "开plus专用", "好底号", "未绑卡"])
    )
    if is_free:
        return "chatgpt-account", True

    refined_tier = chatgpt_tier(f"{clean_identity} {description_text}")
    if refined_tier:
        return refined_tier, True

    if is_sub2api_only or contains(clean_title, [
        "codex plus", "codex plus账号", "codexplus", "codex账号", "codex 账号",
        "codex成品", "codex 成品", "codex独享", "codex 独享"
    ]):
        if contains(clean_title, ["中转", "不限时", "额度", "刀"]) or contains(clean_category, ["中转", "额度"]):
            return None, False
        if is_free:
            return "chatgpt-account", True
        return "chatgpt-plus", True

    if contains(title_text, CHATGPT_AMBIGUOUS_CREDIT_MARKERS):
        return None, False

    if is_free or contains(title_text, CHATGPT_PRODUCT_MARKERS):
        return "chatgpt-account", False

    return None, False


def classify(
    title: str,
    category: str = "",
    raw: dict[str, Any] | None = None,
    *,
    source_platform: str = "",
    price: float | str | Decimal | None = None,
) -> Classification:
    raw = raw or {}
    source_platform = source_platform or str(raw.get("source_platform") or "")
    if price is None and raw:
        price = raw.get("listed_price") if raw.get("listed_price") not in (None, "") else raw.get("price")
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
    if slug == "chatgpt-plus" and price is not None:
        try:
            p_val = float(price)
            if 0 < p_val < 8.00:
                if (
                    contains(detail_text, CHATGPT_FREE_MARKERS)
                    or contains(category_text, ["free", "普号", "白号"])
                    or contains(detail_text, ["底号", "好底号", "未绑卡", "升级", "开plus", "开通plus", "邮箱"])
                ):
                    slug = "chatgpt-account"
                elif is_chatgpt_service(detail_text) or contains(detail_text, ["接码", "接马", "提链", "支付链接"]):
                    slug = "chatgpt-access-service"
                else:
                    risks.append("abnormal_low_price")
        except (ValueError, TypeError):
            pass
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
        is_comparable=bool(slug) and (delivery_type in COMPARABLE_DELIVERY_TYPES),
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
        ("chatgpt-access-service", "OpenAI", "ChatGPT 手机接码", "接码、验证与开通服务", "service", "聚合明确用于 ChatGPT 或 OpenAI 的手机接码、验证与开通服务公开报价。"),
        ("codex-access", "OpenAI", "Codex 账号与访问", "账号、订阅与访问类商品", "account", "已合并至 ChatGPT Plus。"),
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

    price = parse_decimal(record.get("listed_price") if record.get("listed_price") not in (None, "") else record.get("price"))
    currency = normalize_currency(record.get("currency"))
    result = classify(
        raw.original_name,
        raw.original_category,
        raw_json,
        source_platform=str(record.get("source_platform") or shop.platform or ""),
        price=price,
    )
    offer = db.scalar(select(Offer).where(Offer.raw_product_id == raw.id))
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
    is_manually_locked = (not is_new_offer) and (("manual_override" in (offer.tags or [])) or (offer.classification_confidence == 100))
    if not is_manually_locked:
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
    if not is_manually_locked:
        offer.tags = result.tags
        offer.risk_flags = result.risks
        offer.classification_confidence = result.confidence
        offer.delivery_type = result.delivery_type
        offer.is_comparable = bool(result.slug) and (result.delivery_type in COMPARABLE_DELIVERY_TYPES)
        offer.service_period = result.service_period
        offer.warranty = result.warranty
        offer.use_scenarios = result.use_scenarios
        offer.item_fingerprint = result.item_fingerprint
    else:
        current_tags = list(offer.tags or [])
        if "manual_override" not in current_tags:
            current_tags.append("manual_override")
        offer.tags = current_tags
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
