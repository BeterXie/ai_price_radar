from __future__ import annotations

from collections.abc import Iterable, Sequence


BRAND_KEYWORDS: dict[str, list[str]] = {
    "openai": [
        "chatgpt",
        "chatgpt plus",
        "chatgpt pro",
        "chatgpt team",
        "chatgpt business",
        "openai api",
        "codex",
    ],
    "claude": ["claude", "claude pro", "claude api", "anthropic"],
    "gemini": ["gemini", "gemini advanced", "google one ai", "gemini api"],
    "grok": ["grok", "supergrok", "xai api", "x.ai"],
    "developer_tools": ["cursor", "windsurf", "augment", "github copilot"],
}

CHINESE_AUX_KEYWORDS = [
    "账号",
    "成品号",
    "代充",
    "直充",
    "团队席位",
    "车位",
    "卡密",
    "兑换码",
    "API",
    "额度",
    "中转",
    "自动发货",
]


def all_keywords() -> list[str]:
    values: list[str] = []
    for group in BRAND_KEYWORDS.values():
        values.extend(group)
    values.extend(CHINESE_AUX_KEYWORDS)
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def bing_woocommerce_queries(keywords: Sequence[str]) -> list[str]:
    queries = [
        '"ChatGPT Plus" "add to cart"',
        '"Claude Pro" "add to cart"',
        '"Gemini Advanced" "add to cart"',
        '"OpenAI API" "buy"',
        '"ChatGPT Plus" inurl:product',
        '"Claude" inurl:product',
    ]
    for keyword in keywords:
        if str(keyword).strip():
            queries.append(f'"{keyword}" "add to cart"')
    return list(dict.fromkeys(queries))


def bing_schema_org_queries(keywords: Sequence[str]) -> list[str]:
    queries = [
        '"ChatGPT Plus" "priceCurrency"',
        '"Claude Pro" "InStock"',
        '"Gemini Advanced" "Product"',
        '"OpenAI API" "AggregateOffer"',
        '"SuperGrok" "price"',
    ]
    for keyword in keywords:
        if str(keyword).strip():
            queries.append(f'"{keyword}" "Product" "price"')
    return list(dict.fromkeys(queries))


def bing_16688_queries(keywords: Sequence[str] = ()) -> list[str]:
    """Search indexed 16688 shop pages, not product pages, for AI sources.

    Uses a fixed high-value term list rather than a cartesian product of all
    keywords to stay within Bing RSS query budget and minimise low-value noise.
    The ``keywords`` parameter is accepted for interface compatibility but is
    intentionally not used to generate additional queries.
    """
    _ = keywords  # accepted for interface compatibility; not used
    high_value_terms = [
        # Priority 1 – brand / product names
        "ChatGPT",
        "Codex",
        "OpenAI",
        "Claude",
        "Gemini",
        "Grok",
        # Priority 2 – specific plans
        "ChatGPT Plus",
        "ChatGPT Pro",
        "SuperGrok",
        "Claude Pro",
        "Gemini Advanced",
        "OpenAI API",
        # Priority 3 – service / fulfilment keywords
        "Codex 接码",
        "接码",
        "验证码",
        "成品号",
    ]
    return [
        f'site:16688.com.cn/shop "{term}"'
        for term in high_value_terms
    ]


GITHUB_HOMEPAGE_QUERIES = (
    '"AI price" in:name,description,readme is:public',
    '"ChatGPT Plus" "woocommerce" in:readme is:public',
    '"chatgpt" "auto delivery" in:readme is:public',
)
