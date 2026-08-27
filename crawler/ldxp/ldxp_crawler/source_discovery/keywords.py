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
    """Search indexed 16688 shop pages, not product pages, for AI sources."""
    del keywords
    return [
        'site:16688.com.cn/shop "ChatGPT"',
        'site:16688.com.cn/shop "Claude"',
        'site:16688.com.cn/shop "Gemini"',
        'site:16688.com.cn/shop "Grok"',
        'site:16688.com.cn/shop "OpenAI"',
    ]


GITHUB_HOMEPAGE_QUERIES = (
    '"AI price" in:name,description,readme is:public',
    '"ChatGPT Plus" "woocommerce" in:readme is:public',
    '"dujiao-next" in:name,description,readme is:public',
    '"chatgpt" "auto delivery" in:readme is:public',
)
