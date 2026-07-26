from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Offer, OfferHistory, Product, RawProduct, Shop
from .services.classifier import classify_product


PRODUCTS = [
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

DEMO_OFFERS = [
    ("NORTH01", "北岸数字", "ChatGPT Business Team K12 自动拉 无质保", "chatgpt-k12", "43.26", 9, "in_stock", True, 7),
    ("ORBIT88", "轨道补给站", "GPT Team 团队邀请 月付 首登售后", "chatgpt-k12", "49.00", 3, "in_stock", True, 18),
    ("MINTLAB", "薄荷实验室", "ChatGPT Plus 自己账号直充 1个月", "chatgpt-plus", "88.00", 12, "in_stock", False, 11),
    ("MESH77", "网格仓库", "GPT Plus 成品号 秒发 售出不退", "chatgpt-plus", "39.90", 0, "out_of_stock", True, 31),
    ("STACKAI", "栈上 AI", "ChatGPT Pro 20x 会员 月付", "chatgpt-pro-20x", "799.00", 2, "in_stock", False, 25),
    ("APIROOM", "接口仓", "OpenAI API 5美元额度 API Key", "openai-api-credit", "42.00", 20, "in_stock", True, 9),
    ("CLAUDEX", "Claude 交换所", "Claude Pro 一个月 成品号", "claude-pro", "109.00", 5, "in_stock", True, 14),
    ("GEMINIX", "双子补给", "Gemini Advanced Google One AI 1个月", "gemini-advanced", "79.00", 6, "in_stock", False, 21),
    ("GROKX", "Grok 补给站", "SuperGrok 代充值 一个月", "grok-super", "159.00", 4, "in_stock", False, 16),
    ("XPREMIUM", "X 会员补给", "X Premium+ 12个月官方直充", "x-premium-plus", "1598.00", 3, "in_stock", False, 12),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        products: dict[str, Product] = {x.slug: x for x in db.scalars(select(Product))}
        for slug, platform, name, subtitle, product_type, description in PRODUCTS:
            product = products.get(slug)
            if product is None:
                product = Product(slug=slug)
                db.add(product)
                products[slug] = product
            product.platform = platform
            product.display_name = name
            product.subtitle = subtitle
            product.product_type = product_type
            product.description = description
            product.search_keywords = [name, platform, product_type]
        legacy_team = products.get("chatgpt-team-business")
        if legacy_team is not None:
            legacy_team.is_visible = False
        db.flush()
        if db.scalar(select(Offer.id).limit(1)) is not None:
            db.commit()
            return

        now = datetime.now(timezone.utc)
        for token, shop_name, title, slug, price, stock, stock_status, auto_delivery, age_minutes in DEMO_OFFERS:
            shop = Shop(
                token=token,
                name=shop_name,
                source_url=f"https://example.com/shop/{token}",
                status="success",
                source_score=90,
                last_seen_at=now - timedelta(minutes=age_minutes),
                last_success_at=now - timedelta(minutes=age_minutes),
            )
            db.add(shop)
            db.flush()
            raw = RawProduct(
                shop_id=shop.id,
                source_product_key=f"demo-{token}",
                original_name=title,
                source_url=f"https://example.com/item/{token}",
                last_seen_at=now - timedelta(minutes=age_minutes),
            )
            db.add(raw)
            db.flush()
            classification = classify_product(title)
            offer = Offer(
                raw_product_id=raw.id,
                product_id=products[slug].id,
                shop_id=shop.id,
                price=Decimal(price),
                stock_count=stock,
                stock_status=stock_status,
                auto_delivery=auto_delivery,
                tags=classification.tags,
                risk_flags=classification.risk_flags,
                classification_confidence=classification.confidence,
                delivery_type=classification.delivery_type,
                is_comparable=classification.is_comparable,
                service_period=classification.service_period,
                warranty=classification.warranty,
                use_scenarios=classification.use_scenarios,
                item_fingerprint=classification.item_fingerprint,
                source_url=raw.source_url,
                observed_at=raw.last_seen_at,
                active=True,
                approved=True,
            )
            db.add(offer)
            db.flush()
            for days, delta in [(7, Decimal("8.00")), (3, Decimal("3.00")), (0, Decimal("0.00"))]:
                db.add(OfferHistory(
                    offer_id=offer.id,
                    price=Decimal(price) + delta,
                    stock_count=stock,
                    stock_status=stock_status,
                    observed_at=now - timedelta(days=days, minutes=age_minutes),
                ))
        db.commit()


if __name__ == "__main__":
    seed()
