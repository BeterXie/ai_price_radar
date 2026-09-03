from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(slots=True)
class Classification:
    slug: str | None
    tags: list[str]
    risk_flags: list[str]
    confidence: int
    delivery_type: str
    is_comparable: bool
    service_period: str
    warranty: str
    use_scenarios: list[str]
    item_fingerprint: str


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
RELAY_MARKERS = ["中转", "反代", "sub2api", "倍率", "分组"]
SHARED_POOL_MARKERS = ["号池", "共享池", "共享号", "拼车池"]
TRIAL_MARKERS = ["日抛", "体验版", "体验号", "试用号", "小时号"]
GENERIC_EMAIL_MARKERS = ["gmail", "谷歌邮箱", "谷歌邮件", "谷歌账号", "outlook", "hotmail", "icloud", "ic邮箱", "微软邮箱"]
CATEGORY_COMMERCE_MARKERS = ["plus", "pro", "team", "business", "max", "advanced", "ultra", "super", "heavy", "会员", "订阅", "代充", "直充", "充值", "接码", "api", "key", "token", "额度", "成品", "账号", "首登"]
CHATGPT_SERVICE_MARKERS = ["接码", "验证码", "短信验证", "手机验证", "提链", "扫码对接", "二维码生成", "cyber认证", "persona认证"]
CHATGPT_PRODUCT_MARKERS = ["成品", "账号", "已注册", "会员", "订阅", "代充", "直充", "充值"]
CHATGPT_EXPLICIT_PRODUCT_MARKERS = ["成品", "半成品", "账号", "已注册", "会员", "充值", "代充", "直充", "卡密", "cdk", "兑换码"]

TAG_RULES = {
    "Team": ["team", "团队", "车位"],
    "Business": ["business"],
    "K12": ["k12"],
    "邀请": ["邀请", "自动拉", "拉入"],
    "母号": ["母号"],
    "子号": ["子号"],
    "成品号": ["成品号", "账号密码", "普号", "白号"],
    "代充": ["代充"],
    "直充": ["直充"],
    "卡密": ["卡密", "cdk", "兑换码"],
    "API": ["api", "apikey", "api key"],
    "自动发货": ["自动发货", "秒发"],
    "月付": ["月卡", "一个月", "1个月", "30天"],
    "年付": ["年卡", "一年", "12个月", "365天"],
}

RISK_RULES = {
    "无售后": ["无售后", "不售后", "售出不退"],
    "无质保": ["无质保", "不质保"],
    "仅首登保障": ["质保首登", "仅首登", "首登售后"],
    "账号密码交付": ["账号密码", "邮箱密码", "成品号"],
    "团队席位": ["团队邀请", "车位", "自动拉", "拉入团队"],
    "限制退款": ["买错不退", "不可退款", "售出不退"],
    "共享号池": SHARED_POOL_MARKERS,
    "中转服务": RELAY_MARKERS,
    "体验或日抛": TRIAL_MARKERS,
}

COMPARABLE_DELIVERY_TYPES = {
    "subscription_recharge",
    "finished_account",
    "semi_finished_account",
    "team_seat",
    "card_code",
    "api_credit",
}


def normalize_title(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[\s_\-—|/\\]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract(mapping: dict[str, list[str]], text: str) -> list[str]:
    result: list[str] = []
    for label, needles in mapping.items():
        if any(normalize_title(needle) in text for needle in needles):
            result.append(label)
    return result


def _contains(text: str, needles: list[str]) -> bool:
    return any(normalize_title(needle) in text for needle in needles)


def _pro_multiplier(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text).replace("×", "x").replace("✖", "x").replace("倍", "x").replace("\ufe0f", "")
    for multiplier in (20, 5):
        value = str(multiplier)
        if re.search(rf"pro.*?x?{value}x?(?!\d)|(?<!\d){value}x?.*?pro", compact):
            return multiplier
    return None


def _delivery_type(text: str) -> str:
    account_markers = ["成品", "半成品", "账号", "首登", "已接码", "未接码", "账号密码", "独享"]
    if _contains(text, CHATGPT_SERVICE_MARKERS) and not _contains(text, account_markers):
        return "verification_service"
    if _contains(text, SHARED_POOL_MARKERS):
        return "shared_pool"
    if _contains(text, RELAY_MARKERS) and not _contains(text, account_markers):
        return "relay_api"
    if _contains(text, ["api额度", "api 额度", "api余额", "api 余额", "api key", "apikey", "token额度"]):
        return "api_credit"
    if _contains(text, ["团队邀请", "team seat", "车位", "自动拉", "拉入团队", "子号"]):
        return "team_seat"
    if _contains(text, TRIAL_MARKERS):
        return "trial_account"
    if _contains(text, ["卡密", "cdk", "兑换码"]):
        return "card_code"
    if _contains(text, ["半成品", "首登号", "未接码"]):
        return "semi_finished_account"
    if _contains(text, ["成品", "账号密码", "邮箱密码", "已接码", "独享账号", "账号"]):
        return "finished_account"
    if _contains(text, ["官方充值", "官方直充", "直充", "代充", "充值", "订阅"]):
        return "subscription_recharge"
    if _contains(text, RELAY_MARKERS):
        return "relay_api"
    return "unknown"


def _service_period(text: str) -> str:
    if _contains(text, ["年卡", "一年", "1年", "12个月", "365天", "年付"]):
        return "one_year"
    if _contains(text, ["六个月", "6个月", "半年", "半年卡"]):
        return "six_months"
    if _contains(text, ["三个月", "3个月", "季度", "季卡"]):
        return "three_months"
    if _contains(text, ["月卡", "一个月", "1个月", "30天", "月付"]):
        return "one_month"
    if _contains(text, ["周卡", "一周", "1周", "7天"]):
        return "one_week"
    if _contains(text, ["日抛", "一天", "1天", "24小时", "24h"]):
        return "one_day"
    return "unknown"


def _warranty(text: str) -> str:
    if _contains(text, ["无质保", "不质保"]):
        return "none"
    if _contains(text, ["质保首登", "仅首登", "首登售后", "首登质保"]):
        return "first_login"
    if re.search(r"质保.{0,4}(1\s*小时|一\s*小时)|(?:1\s*小时|一\s*小时).{0,4}质保", text):
        return "one_hour"
    if re.search(r"质保.{0,4}(24\s*小时|1\s*天|一\s*天)|(?:24\s*小时|1\s*天|一\s*天).{0,4}质保", text):
        return "one_day"
    if re.search(r"质保.{0,4}(3\s*天|三\s*天)|(?:3\s*天|三\s*天).{0,4}质保", text):
        return "three_days"
    if re.search(r"质保.{0,4}(7\s*天|七\s*天)|(?:7\s*天|七\s*天).{0,4}质保", text):
        return "seven_days"
    if _contains(text, ["全程质保", "订阅期质保", "质保到期"]):
        return "subscription_term"
    return "unknown"


def _use_scenarios(text: str) -> list[str]:
    rules = [
        ("web", ["网页", "web"]),
        ("desktop", ["客户端", "app", "桌面端"]),
        ("codex", ["codex"]),
        ("api", ["api", "apikey", "api key"]),
        ("relay", ["中转", "反代"]),
    ]
    return [label for label, markers in rules if _contains(text, markers)]


def _fingerprint_component(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value.casefold())
    value = re.sub(r"(?<!\d)\d{1,2}\s*[./-]\s*\d{1,2}(?!\d)", " ", value)
    value = re.sub(r"(?<!\d)\d{1,2}\s*点(?!\d)", " ", value)
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def _item_fingerprint(title: str, description: str, slug: str | None, delivery_type: str, period: str, warranty: str) -> str:
    payload = "|".join([
        slug or "unclassified",
        _fingerprint_component(title),
        _fingerprint_component(description)[:2000],
        delivery_type,
        period,
        warranty,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chatgpt_tier(text: str) -> str | None:
    if _contains(text, CHATGPT_K12_MARKERS):
        return "chatgpt-k12"
    multiplier = _pro_multiplier(text)
    if multiplier == 20:
        return "chatgpt-pro-20x"
    if multiplier == 5:
        return "chatgpt-pro-5x"
    if _contains(text, ["(cx", "分组", "不限时"]):
        return None
    if _contains(text, CHATGPT_PRO_MARKERS):
        return "chatgpt-pro"
    if _contains(text, CHATGPT_PLUS_MARKERS):
        if _contains(text, ["(cx", "分组", "不限时"]):
            return None
        if re.search(r"(?<!\d)(?:1|2|3|4|5|6|7|8|9|10|15|25|30|50|100|200|300|500|1000)\s*[刀$]", text):
            if not re.search(r"(?<!\d)20\s*[刀$]", text):
                return None
        if re.search(r"\bapi\b", text, re.IGNORECASE) and not _contains(text, ["代充", "直充", "充值", "月卡", "30天", "成品"]):
            return None
        return "chatgpt-plus"
    return None


def _explicit_brands(text: str) -> list[str]:
    return [brand for brand, markers in BRAND_MARKERS.items() if _contains(text, markers)]


def _first_title_brand(text: str) -> str | None:
    if _contains(text, ["openai codex", "open ai codex"]):
        return "codex"
    positions: list[tuple[int, str]] = []
    for brand, markers in BRAND_MARKERS.items():
        for marker in markers:
            position = text.find(normalize_title(marker))
            if position >= 0:
                positions.append((position, brand))
    return min(positions)[1] if positions else None


def _detect_brand(title_text: str, category_text: str) -> str | None:
    title_brand = _first_title_brand(title_text)
    if title_brand:
        return title_brand

    if "plus" in title_text and _contains(title_text, IMPLICIT_CHATGPT_MARKERS) and not _contains(title_text, NON_TARGET_PLUS_MARKERS):
        return "chatgpt"

    category_brands = _explicit_brands(category_text)
    if len(category_brands) == 1:
        if _contains(title_text, GENERIC_EMAIL_MARKERS):
            return None
        if _contains(title_text, CATEGORY_COMMERCE_MARKERS):
            return category_brands[0]
    if len(category_brands) > 1:
        return None
    return None


def _compact_latin(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _16688_chatgpt_alias_tier(value: str) -> str | None:
    compact = _compact_latin(value)
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


def _16688_grok_alias(value: str) -> str | None:
    compact = _compact_latin(value)
    if any(marker in compact for marker in ("groheavy", "grosuper", "supergro")):
        return "grok-super"
    if "grofree" in compact:
        return "grok-account"
    return None


def _classify_16688_alias(
    title_text: str,
    category_text: str,
    description_text: str,
) -> str | None:
    if (
        _contains(title_text, CHATGPT_NON_PRODUCT_MARKERS)
        and not _contains(title_text, CHATGPT_EXPLICIT_PRODUCT_MARKERS)
    ) or _contains(title_text, NON_TARGET_PLUS_MARKERS):
        return None

    alias_identity = normalize_title(" ".join([title_text, category_text]))
    if _contains(alias_identity, NON_TARGET_PLUS_MARKERS) or _contains(alias_identity, GENERIC_EMAIL_MARKERS):
        return None

    has_chatgpt_alias = _16688_chatgpt_alias_tier(alias_identity) is not None or _contains(
        alias_identity,
        BRAND_MARKERS["chatgpt"],
    )
    if has_chatgpt_alias and _contains(alias_identity, CHATGPT_API_MARKERS):
        if _contains(alias_identity, ["中转", "倍率"]):
            return None
        return "openai-api-credit"

    title_grok = _16688_grok_alias(title_text)
    if title_grok:
        return title_grok
    title_alias = _16688_chatgpt_alias_tier(title_text)
    if title_alias:
        return title_alias

    title_plain_tier = None
    if _contains(title_text, CHATGPT_PLUS_MARKERS):
        title_plain_tier = "chatgpt-plus"
    elif _contains(title_text, CHATGPT_GO_MARKERS):
        title_plain_tier = "chatgpt-go"
    elif _contains(title_text, CHATGPT_PRO_MARKERS):
        title_plain_tier = "chatgpt-pro"

    context = " ".join([category_text, description_text])
    context_grok = _16688_grok_alias(context)
    context_chatgpt = _16688_chatgpt_alias_tier(context)
    if title_plain_tier and context_chatgpt:
        return title_plain_tier
    if context_grok and not context_chatgpt and _contains(title_text, CATEGORY_COMMERCE_MARKERS):
        return context_grok
    if context_chatgpt and _contains(title_text, CATEGORY_COMMERCE_MARKERS):
        return context_chatgpt
    return None


def _classify_identity(
    title_text: str,
    category_text: str,
    description_text: str = "",
    source_platform: str = "",
) -> tuple[str | None, bool]:
    identity_text = normalize_title(" ".join([title_text, category_text]))
    tier_text = normalize_title(" ".join([identity_text, description_text]))
    if _contains(identity_text, ["(cx", "分组", "中转站"]):
        return None, False
    if _contains(identity_text, RELAY_MARKERS) and _contains(identity_text, ["api", "key", "token", "额度"]):
        return None, False
    brand = _detect_brand(title_text, category_text)
    if brand is None:
        if str(source_platform or "").strip().casefold() == PLATFORM_16688:
            alias_slug = _classify_16688_alias(title_text, category_text, description_text)
            if alias_slug:
                return alias_slug, True
        return None, False

    if brand == "codex":
        if _contains(identity_text, ["(cx", "分组", "中转站"]):
            return None, False
        return "codex-access", True
    if brand == "claude":
        if _contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "claude-api-access", True
        if _contains(identity_text, ["claude pro", "claude会员", "claude 会员"]):
            return "claude-pro", True
        return "claude-account", False
    if brand == "gemini":
        if _contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "gemini-api-access", True
        if _contains(identity_text, ["gemini advanced", "gemini pro会员", "google one ai"]):
            return "gemini-advanced", True
        return "gemini-account", False
    if brand == "grok":
        if _contains(identity_text, ["api", "api key", "apikey", "token", "额度"]):
            return "grok-api-access", True
        if _contains(identity_text, ["supergrok", "super grok", "grok super"]):
            return "grok-super", True
        return "grok-account", False
    if brand == "x":
        if _contains(identity_text, ["premium business", "premium organization", "premium organisation", "企业认证", "金标", "灰标"]):
            return None, False
        if _contains(identity_text, ["premium+", "premium +", "premium plus", "premiumplus"]):
            return "x-premium-plus", True
        if _contains(identity_text, ["basic", "基础版"]):
            return "x-premium-basic", True
        if _contains(identity_text, ["premium", "twitter blue", "推特会员", "蓝v", "蓝标"]):
            return "x-premium", True
        return None, False

    if _contains(identity_text, CHATGPT_API_MARKERS):
        if _contains(identity_text, ["中转", "倍率"]):
            return None, False
        return "openai-api-credit", True
    if (
        _contains(title_text, CHATGPT_NON_PRODUCT_MARKERS)
        and not _contains(title_text, CHATGPT_EXPLICIT_PRODUCT_MARKERS)
    ):
        return None, False
    if (_contains(title_text, CHATGPT_SERVICE_MARKERS) and not _contains(title_text, CHATGPT_PRODUCT_MARKERS)) or (
        _contains(title_text, GENERIC_EMAIL_MARKERS) and not _contains(title_text, CHATGPT_PRODUCT_MARKERS)
    ):
        return "chatgpt-access-service", True
    if _contains(title_text, CHATGPT_FREE_MARKERS):
        return "chatgpt-account", True
    if _contains(title_text, CHATGPT_GO_MARKERS):
        return "chatgpt-go", True
    title_tier = _chatgpt_tier(title_text)
    if title_tier:
        return title_tier, True
    refined_tier = _chatgpt_tier(tier_text)
    if refined_tier and refined_tier != "chatgpt-plus":
        return refined_tier, True
    if _contains(title_text, CHATGPT_AMBIGUOUS_CREDIT_MARKERS):
        return None, False
    if _contains(title_text, CHATGPT_PRODUCT_MARKERS):
        return "chatgpt-account", False
    return None, False


def classify_product(
    title: str,
    category: str = "",
    description: str = "",
    *,
    source_platform: str = "",
) -> Classification:
    detail_text = normalize_title(" ".join([title, category, description]))
    tags = _extract(TAG_RULES, detail_text)
    risks = _extract(RISK_RULES, detail_text)
    slug, specific_match = _classify_identity(
        normalize_title(title),
        normalize_title(category),
        normalize_title(description),
        source_platform,
    )
    if slug != "chatgpt-k12":
        tags = [tag for tag in tags if tag not in {"Team", "Business", "K12", "邀请", "母号", "子号"}]
    confidence = 88 if specific_match else 68 if slug else 0
    delivery_type = _delivery_type(normalize_title(title))
    if delivery_type == "unknown":
        delivery_type = _delivery_type(detail_text)
    period = _service_period(normalize_title(title))
    if period == "unknown":
        described_period = _service_period(detail_text)
        if described_period not in {"one_day", "one_week"}:
            period = described_period
    warranty = _warranty(normalize_title(title))
    if warranty == "unknown":
        warranty = _warranty(detail_text)
    return Classification(
        slug=slug,
        tags=tags,
        risk_flags=risks,
        confidence=confidence,
        delivery_type=delivery_type,
        is_comparable=delivery_type in COMPARABLE_DELIVERY_TYPES,
        service_period=period,
        warranty=warranty,
        use_scenarios=_use_scenarios(detail_text),
        item_fingerprint=_item_fingerprint(title, description, slug, delivery_type, period, warranty),
    )


def normalize_stock(value: str | None, stock_count: int | None) -> str:
    text = normalize_title(value or "")
    if any(word in text for word in ["有货", "in stock", "available"]):
        return "in_stock"
    if any(word in text for word in ["缺货", "售罄", "out of stock"]):
        return "out_of_stock"
    if any(word in text for word in ["下架", "不可用", "关闭", "暂停"]):
        return "unavailable"
    if stock_count is not None:
        return "in_stock" if stock_count > 0 else "out_of_stock"
    return "unknown"
