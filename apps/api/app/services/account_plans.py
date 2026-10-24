"""Account tiers shared by ingestion and admin reclassification.

Model names and delivery forms are not account tiers. Resolve from the title
first; a broad shop category must never override an explicit SKU variant.
"""
from __future__ import annotations

import re

SUBSCRIPTION_MARKERS = ("会员", "订阅", "套餐", "代充", "直充", "月卡", "年卡", "日卡", "subscription")


# Existing public slugs remain identifiers; their labels describe the actual plan.
PLAN_PRODUCTS = [
    ("chatgpt-pro", "OpenAI", "ChatGPT Pro（倍率未注明）", "未注明 5x / 20x；不猜测用量档位"),
    ("chatgpt-business", "OpenAI", "ChatGPT Business", "Business / 原 Team 团队套餐"),
    ("chatgpt-edu", "OpenAI", "ChatGPT Edu", "明确标注 Edu 的教育套餐"),
    ("chatgpt-enterprise", "OpenAI", "ChatGPT Enterprise", "企业套餐"),
    ("claude-pro", "Claude", "Claude Pro", "Pro 个人套餐；不等同于 Max 5x"),
    ("claude-max-5x", "Claude", "Claude Max 5x", "Max 5x 用量档位"),
    ("claude-pro-20x", "Claude", "Claude Max 20x", "Max 20x 用量档位"),
    ("claude-max", "Claude", "Claude Max（倍率未注明）", "不猜测 5x / 20x"),
    ("claude-enterprise", "Claude", "Claude Enterprise", "企业套餐"),
    ("claude-subscription", "Claude", "Claude 订阅（等级未注明）", "已标注订阅，但不能确认具体套餐"),
    ("gemini-plus", "Gemini", "Google AI Plus", "Google AI Plus 账号套餐"),
    ("gemini-pro", "Gemini", "Google AI Pro", "Google AI Pro 账号套餐；不是 Pro 模型名"),
    ("gemini-ultra", "Gemini", "Google AI Ultra（倍率未注明）", "Ultra 套餐；不猜测倍率"),
    ("gemini-ultra-5x", "Gemini", "Google AI Ultra 5x", "明确标注 Ultra 5x"),
    ("gemini-ultra-20x", "Gemini", "Google AI Ultra 20x", "明确标注 Ultra 20x"),
    ("gemini-subscription", "Gemini", "Google AI 订阅（等级未注明）", "不能仅凭 Google One AI 推断等级"),
    ("gemini-advanced", "Gemini", "Gemini Advanced（历史名称）", "保留明确 Advanced 标记；不推断当前套餐权益"),
    ("grok-heavy", "Grok", "SuperGrok Heavy", "独立于 SuperGrok 的 Heavy 套餐"),
    ("grok-plus", "Grok", "Grok Plus", "Plus 套餐"),
    ("grok-premium", "Grok", "Grok Premium", "Premium 套餐"),
    ("grok-plan-super", "Grok", "Grok Super", "Super 套餐；不等同于旧 SuperGrok"),
    ("grok-ultra", "Grok", "Grok Ultra", "Ultra 套餐"),
    ("grok-subscription", "Grok", "Grok 订阅（等级未注明）", "已标注订阅，但不能确认具体套餐"),
    ("cursor-pro-plus", "Cursor", "Cursor Pro+", "Pro Plus 个人套餐"),
    ("cursor-ultra", "Cursor", "Cursor Ultra", "Ultra；套餐版本以来源说明为准"),
    ("cursor-plus", "Cursor", "Cursor Plus", "Plus 套餐"),
    ("cursor-premium", "Cursor", "Cursor Premium", "Premium 套餐"),
    ("cursor-super", "Cursor", "Cursor Super", "Super 套餐"),
    ("cursor-business", "Cursor", "Cursor Teams / Business", "团队席位；区别于个人套餐"),
    ("cursor-enterprise", "Cursor", "Cursor Enterprise", "企业套餐"),
    ("cursor-subscription", "Cursor", "Cursor 订阅（等级未注明）", "不把日卡或未注明等级的订阅当作 Pro"),
]


def product_definitions(definitions: list[tuple]) -> list[tuple]:
    result = {row[0]: row for row in definitions}
    for slug, brand, name, subtitle in PLAN_PRODUCTS:
        result[slug] = (slug, brand, name, subtitle, "subscription", f"聚合 {name} 的公开报价。{subtitle}。")
    result["chatgpt-k12"] = (
        "chatgpt-k12", "OpenAI", "ChatGPT K12（商家标记）", "商家 K12 标签；不等同于 Business / Edu",
        "subscription", "保留明确标注 K12 的商家报价；该标签不代表已核验的官方套餐。",
    )
    return list(result.values())


def _word(text: str, word: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9])(?:{word})(?![a-z0-9])", text, re.I))


def _tier(brand: str, text: str) -> str | None:
    if brand in ("claude", "cursor"):
        if _word(text, "enterprise") or "企业版" in text:
            return {"claude": "claude-enterprise", "cursor": "cursor-enterprise"}[brand]
        if _word(text, "team(?:s)?|business") or any(x in text for x in ("团队版", "团队套餐", "团队会员")):
            return {"claude": "claude-team", "cursor": "cursor-business"}[brand]
    if brand == "claude":
        if re.search(r"(?<!\d)(?:20\s*(?:x|倍)|x\s*20)(?!\d)", text):
            return "claude-pro-20x"
        if re.search(r"(?<!\d)(?:5\s*(?:x|倍)|x\s*5)(?!\d)", text):
            return "claude-max-5x"
        if _word(text, "max"):
            return "claude-max"
        if _word(text, "pro"):
            return "claude-pro"
    elif brand == "gemini":
        if _word(text, "advanced"):
            return "gemini-advanced"
        official_plan = re.search(r"google\s*(?:one\s*)?ai\s*(?:plus|pro|ultra)(?![a-z])", text)
        subscription = any(word in text for word in SUBSCRIPTION_MARKERS)
        # Gemini Pro / Ultra also name models. A model version or bare model
        # access does not establish a Google AI account subscription.
        if not official_plan and (re.search(r"gemini\s*\d", text) or not subscription):
            return None
        if _word(text, "ultra"):
            if re.search(r"(?<!\d)20\s*(?:x|倍)(?!\d)", text):
                return "gemini-ultra-20x"
            if re.search(r"(?<!\d)5\s*(?:x|倍)(?!\d)", text):
                return "gemini-ultra-5x"
            return "gemini-ultra"
        if _word(text, "plus"):
            return "gemini-plus"
        # "Gemini 2.5 Pro" names a model, not a subscription.
        if re.search(r"google\s*(?:one\s*)?ai\s*pro|gemini\s*pro(?![a-z])", text) or (
            not re.search(r"gemini\s*\d", text) and re.search(r"(?<![a-z])pro\s*(?:会员|订阅|套餐|年卡|月卡)", text)
        ):
            return "gemini-pro"
    elif brand == "grok":
        if _word(text, "heavy"):
            return "grok-heavy"
        if re.search(r"super\s*gro(?:k)?(?![a-z])", text):
            return "grok-super"
        if re.search(r"grok\s*super(?![a-z])", text):
            return "grok-plan-super"
        for word, slug in (("ultra", "grok-ultra"), ("premium", "grok-premium"), ("plus", "grok-plus"), ("super", "grok-plan-super")):
            if _word(text, word):
                return slug
    elif brand == "cursor":
        if _word(text, "ultra"):
            return "cursor-ultra"
        if re.search(r"(?<![a-z])pro\s*(?:\+|plus)(?![a-z])", text):
            return "cursor-pro-plus"
        for word in ("premium", "super", "plus", "pro"):
            if _word(text, word):
                return f"cursor-{word}"
    if brand in ("claude", "cursor") and "团队" in text:
        return {"claude": "claude-team", "cursor": "cursor-business"}[brand]
    return None


def account_plan(brand: str, title: str, category: str, description: str = "") -> str | None:
    title = title.replace("×", "x").replace("✖", "x")
    category = category.replace("×", "x").replace("✖", "x")
    # Do not promote free / upgrade-ready accounts because the category says Pro.
    if any(x in title for x in ("底号", "可升级", "不含会员", "未订阅", "免费账号", "免费账户", "普通账号", "普通帐号", "普号", "白号")) or _word(title, "free|hobby"):
        return f"{brand}-account"
    explicit = _tier(brand, title)
    if brand == "gemini" and explicit is None and re.search(r"gemini\s*(?:\d|(?:pro|ultra|flash)(?![a-z]))", title):
        # An explicit model SKU must not be promoted by a broad paid category
        # or a generic marketing description after title matching declined it.
        if any(word in title for word in SUBSCRIPTION_MARKERS):
            return "gemini-subscription"
        return "gemini-account"
    explicit = explicit or _tier(brand, category)
    if explicit:
        return explicit
    # Descriptions may describe a single SKU; generic feature lists must not
    # promote an otherwise unidentified account to a paid tier.
    brands = [name for name in ("claude", "gemini", "grok", "cursor", "chatgpt") if name in description]
    if brands == [brand] and any(word in description for word in ("本商品", "商品内容", "会员", "订阅", "成品", "subscription")):
        described = _tier(brand, description)
        if described:
            return described
    if any(word in title for word in (*SUBSCRIPTION_MARKERS, "google one ai")):
        return f"{brand}-subscription"
    return None


def ensure_account_plans(db) -> None:
    from sqlalchemy import select
    from ..models import Product

    existing = {row.slug: row for row in db.scalars(select(Product))}
    for slug, brand, name, subtitle, kind, description in product_definitions([]):
        product = existing.get(slug)
        if product is None:
            product = Product(slug=slug)
            db.add(product)
        product.platform = brand
        product.display_name = name
        product.subtitle = subtitle
        product.product_type = kind
        product.description = description
        product.search_keywords = [brand, name]
        if slug == "chatgpt-pro":
            # Earlier seed/import code forcibly hid this category.
            product.is_visible = True
    db.flush()
