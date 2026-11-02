"""Shared public catalog labels and search aliases; no database access."""
from __future__ import annotations

from typing import Any
import re
import unicodedata

from .account_plans import PLAN_PRODUCTS, canonical_product_slug

DELIVERY_LABELS: dict[str, str] = {
    "subscription_recharge": "官方直充 / 代充",
    "finished_account": "成品账号",
    "semi_finished_account": "半成品 / 首登号",
    "team_seat": "团队席位",
    "card_code": "卡密 / 兑换码",
    "trial_account": "日抛 / 体验号",
    "shared_pool": "共享号池",
    "relay_api": "中转 / 反代",
    "api_credit": "API 额度",
    "verification_service": "验证 / 接码服务",
    "unknown": "形态待确认",
}

PERIOD_LABELS: dict[str, str] = {
    "one_day": "1 天 / 日抛",
    "one_week": "1 周",
    "one_month": "1 个月",
    "three_months": "3 个月",
    "six_months": "6 个月",
    "one_year": "1 年",
    "unknown": "期限未注明",
}

WARRANTY_LABELS: dict[str, str] = {
    "none": "无质保",
    "first_login": "仅首登质保",
    "one_hour": "1 小时质保",
    "one_day": "24 小时质保",
    "three_days": "3 天质保",
    "seven_days": "7 天质保",
    "subscription_term": "订阅期全保",
    "unknown": "质保未注明",
}

def _normalize_query_alias(value: str) -> str:
    return "".join(value.split()).casefold()


BRAND_GROUPS: dict[str, dict[str, Any]] = {
    "Claude": {
        "title": "Claude 全系列最低报价一览",
        "aliases": ["claude", "anthropic", "克劳德"],
        "hint": "发送具体套餐（如「claude pro」、「claude max 5x」、「claude max 20x」、「claude team」）可查看最低价与店铺详情。",
    },
    "OpenAI": {
        "title": "OpenAI / ChatGPT 全系列最低报价一览",
        "aliases": ["openai", "chatgpt", "gpt"],
        "hint": "发送具体型号（如「chatgpt plus」、「chatgpt 5x」、「chatgpt 20x」、「chatgpt go」）可查看最低价与店铺详情。",
    },
    "Gemini": {
        "title": "Gemini 全系列最低报价一览",
        "aliases": ["gemini", "google", "双子座", "谷歌ai"],
        "hint": "发送具体套餐（如「gemini pro」、「gemini ultra」、「gemini账号」）可查看最低价与店铺详情。",
    },
    "Grok": {
        "title": "Grok 全系列最低报价一览",
        "aliases": ["grok", "xai", "x.ai"],
        "hint": "发送具体型号（如「supergrok」、「grok api」）可查看最低价与店铺详情。",
    },
    "X": {
        "title": "X (Twitter) Premium 全系列最低报价一览",
        "aliases": ["x", "twitter", "推特", "x会员"],
        "hint": "发送具体型号（如「premium」、「premium+」）可查看最低价与店铺详情。",
    },
    "Cursor": {
        "title": "Cursor 全系列最低报价一览",
        "aliases": ["cursor", "cursor会员"],
        "hint": "发送具体型号（如「cursor pro」、「cursor账号」）可查看最低价与店铺详情。",
    },
}

BRAND_ALIASES: dict[str, str] = {}
for brand_key, cfg in BRAND_GROUPS.items():
    for alias in cfg["aliases"]:
        BRAND_ALIASES[_normalize_query_alias(alias)] = brand_key

# Aliases mapped to canonical product slugs for single-product deep dive
PRODUCT_ALIASES: dict[str, str] = {
    # ChatGPT / OpenAI models
    "plus": "chatgpt-plus",
    "chatgpt plus": "chatgpt-plus",
    "gpt plus": "chatgpt-plus",
    "chatgpt-plus": "chatgpt-plus",
    "gpt 5x": "chatgpt-pro-5x",
    "chatgpt 5x": "chatgpt-pro-5x",
    "chatgpt pro 5x": "chatgpt-pro-5x",
    "chatgpt-pro-5x": "chatgpt-pro-5x",
    "gpt 20x": "chatgpt-pro-20x",
    "chatgpt 20x": "chatgpt-pro-20x",
    "chatgpt pro 20x": "chatgpt-pro-20x",
    "chatgpt-pro-20x": "chatgpt-pro-20x",
    "chatgpt pro": "chatgpt-pro",
    "gpt pro": "chatgpt-pro",
    "chatgpt-pro": "chatgpt-pro",
    "go": "chatgpt-go",
    "chatgpt go": "chatgpt-go",
    "gpt go": "chatgpt-go",
    "codex go": "chatgpt-go",
    "chatgpt-go": "chatgpt-go",
    "team": "chatgpt-business",
    "gpt team": "chatgpt-business",
    "chatgpt team": "chatgpt-business",
    "k12": "chatgpt-k12",
    "团队": "chatgpt-business",
    "车位": "chatgpt-business",
    "chatgpt-k12": "chatgpt-k12",
    "gpt 账号": "chatgpt-account",
    "chatgpt 账号": "chatgpt-account",
    "chatgpt free": "chatgpt-account",
    "free": "chatgpt-account",
    "chatgpt-account": "chatgpt-account",
    "chatgpt 接码": "chatgpt-access-service",
    "chatgpt 手机接码": "chatgpt-access-service",
    "openai 接码": "chatgpt-access-service",
    "手机接码": "chatgpt-access-service",
    "chatgpt-access-service": "chatgpt-access-service",
    "openai api": "openai-api-credit",
    "openai-api-credit": "openai-api-credit",
    # Claude models
    "pro": "claude-pro",
    "claude pro": "claude-pro",
    "claude-pro": "claude-pro",
    "5x": "claude-max-5x",
    "claude 5x": "claude-max-5x",
    "claude max": "claude-max",
    "20x": "claude-pro-20x",
    "claude 20x": "claude-pro-20x",
    "claude pro 20x": "claude-pro-20x",
    "claude max 20x": "claude-pro-20x",
    "claude-pro-20x": "claude-pro-20x",
    "claude team": "claude-team",
    "claude-team": "claude-team",
    "claude 车位": "claude-team",
    "claude 团队": "claude-team",
    "claude 账号": "claude-account",
    "claude-account": "claude-account",
    "claude api": "claude-api-access",
    "claude-api-access": "claude-api-access",
    # Gemini models
    "gemini advanced": "gemini-advanced",
    "gemini pro": "gemini-pro",
    "gemini plus": "gemini-plus",
    "gemini ultra": "gemini-ultra",
    "gemini ultra 5x": "gemini-ultra-5x",
    "gemini ultra 20x": "gemini-ultra-20x",
    "gemini-advanced": "gemini-advanced",
    "advanced": "gemini-advanced",
    "gemini 账号": "gemini-account",
    "gemini-account": "gemini-account",
    "gemini api": "gemini-api-access",
    "gemini-api-access": "gemini-api-access",
    # Grok models
    "grok super": "grok-plan-super",
    "grok-super": "grok-super",
    "supergrok": "grok-super",
    "grok 账号": "grok-account",
    "grok-account": "grok-account",
    "grok api": "grok-api-access",
    "grok-api-access": "grok-api-access",
    # X Premium models
    "premium basic": "x-premium-basic",
    "x premium basic": "x-premium-basic",
    "x-premium-basic": "x-premium-basic",
    "premium": "x-premium",
    "x premium": "x-premium",
    "x-premium": "x-premium",
    "premium+": "x-premium-plus",
    "premium plus": "x-premium-plus",
    "x premium+": "x-premium-plus",
    "x premium plus": "x-premium-plus",
    "x-premium-plus": "x-premium-plus",
    # Others
    "deepseek": "deepseek-r1",
    "codex": "chatgpt-plus",
    "codex plus": "chatgpt-plus",
    "api": "openai-api-credit",
    # Cursor models
    "cursor": "cursor-pro",
    "cursor pro": "cursor-pro",
    "cursor-pro": "cursor-pro",
    "cursor pro plus": "cursor-pro-plus",
    "cursor teams": "cursor-business",
    "cursor business": "cursor-business",
    "cursor-business": "cursor-business",
    "cursor 账号": "cursor-account",
    "cursor-account": "cursor-account",
}
for slug, _brand, name, _subtitle in PLAN_PRODUCTS:
    PRODUCT_ALIASES[slug] = slug
    PRODUCT_ALIASES[name] = slug
PRODUCT_ALIASES = {_normalize_query_alias(alias): canonical_product_slug(slug) for alias, slug in PRODUCT_ALIASES.items()}


def product_search_aliases(slug: str, name: str) -> list[str]:
    """Publish product aliases once so snapshot readers need no classifier."""
    return sorted({slug, name, *(alias for alias, target in PRODUCT_ALIASES.items() if target == slug)})


def normalize_search(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).casefold())


def account_access(title: str, delivery_type: str) -> str:
    """Only explicit access claims qualify; a finished account is not necessarily exclusive."""
    text = normalize_search(title)
    positive_shared = re.sub(r"非共享|不共享|不是共享|不含共享", "", text)
    if delivery_type == "shared_pool" or any(word in positive_shared for word in ("共享", "拼车", "号池")):
        return "shared"
    if re.search(r"(?<![不非])独享|独立账号|一人一号|非共享|不共享", text):
        return "exclusive"
    return "unknown"
