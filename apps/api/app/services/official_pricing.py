from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OfficialPriceReference:
    provider: str
    plan: str
    price: Decimal | None
    currency: str
    billing_period: str
    url: str
    checked_at: date
    note: str


CHECKED_AT = date(2026, 7, 29)

# Official list prices are references, not currency conversions. Localized pricing,
# taxes, app-store fees, promotions and availability can differ by region.
OFFICIAL_REFERENCES: dict[str, OfficialPriceReference] = {
    "chatgpt-plus": OfficialPriceReference(
        provider="OpenAI",
        plan="ChatGPT Plus",
        price=Decimal("20.00"),
        currency="USD",
        billing_period="month",
        url="https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus",
        checked_at=CHECKED_AT,
        note="美国网页公开月价；OpenAI 支持多币种与本地化结算，税费和应用商店价格可能不同。",
    ),
    "claude-pro": OfficialPriceReference(
        provider="Anthropic",
        plan="Claude Pro",
        price=Decimal("20.00"),
        currency="USD",
        billing_period="month",
        url="https://support.anthropic.com/en/articles/8325610-how-much-does-claude-pro-cost",
        checked_at=CHECKED_AT,
        note="美国公开月价；部分地区使用本地货币，税费和年付折扣可能不同。",
    ),
    "gemini-advanced": OfficialPriceReference(
        provider="Google",
        plan="Google AI Pro",
        price=Decimal("19.99"),
        currency="USD",
        billing_period="month",
        url="https://one.google.com/about/plans",
        checked_at=CHECKED_AT,
        note="美国公开月价；Google AI 方案名称、存储权益、促销和地区可用性可能变化。",
    ),
    "grok-super": OfficialPriceReference(
        provider="xAI",
        plan="SuperGrok",
        price=Decimal("30.00"),
        currency="USD",
        billing_period="month",
        url="https://x.ai/pricing",
        checked_at=CHECKED_AT,
        note="美国公开月价；地区、税费、支付渠道、促销和产品权益可能变化。",
    ),
    "x-premium-basic": OfficialPriceReference(
        provider="X",
        plan="X Premium Basic",
        price=Decimal("3.00"),
        currency="USD",
        billing_period="month",
        url="https://help.x.com/en/using-x/x-premium",
        checked_at=CHECKED_AT,
        note="美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    ),
    "x-premium": OfficialPriceReference(
        provider="X",
        plan="X Premium",
        price=Decimal("8.00"),
        currency="USD",
        billing_period="month",
        url="https://help.x.com/en/using-x/x-premium",
        checked_at=CHECKED_AT,
        note="美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    ),
    "x-premium-plus": OfficialPriceReference(
        provider="X",
        plan="X Premium+",
        price=Decimal("40.00"),
        currency="USD",
        billing_period="month",
        url="https://help.x.com/en/using-x/x-premium",
        checked_at=CHECKED_AT,
        note="美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    ),
}


def official_reference_for(slug: str) -> OfficialPriceReference | None:
    return OFFICIAL_REFERENCES.get(slug)
