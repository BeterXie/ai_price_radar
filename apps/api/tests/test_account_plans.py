import pytest

from app.services.classifier import classify_product


@pytest.mark.parametrize(("title", "category", "slug"), [
    ("Claude Pro 成品月卡", "Claude Max", "claude-pro"),
    ("Claude Max 5x 代充", "Claude Pro", "claude-max-5x"),
    ("Claude Max 20× 成品号", "Claude Pro", "claude-pro-20x"),
    ("Claude Max 会员", "Claude", "claude-max"),
    ("Claude Enterprise 订阅", "Claude Pro", "claude-enterprise"),
    ("Claude Free 可升级 Pro 底号", "Claude Pro", "claude-account"),
    ("Claude 免费账号", "Claude Pro", "claude-account"),
    ("Claude 普通账号", "Claude Max", "claude-account"),
    ("Claude 白号", "Claude Pro", "claude-account"),
    ("Claude Pro 共享席位", "Claude Team", "claude-pro"),
    ("Claude Max 5x 车位", "Claude Team", "claude-max-5x"),
    ("Google AI Plus 月卡", "Gemini", "gemini-plus"),
    ("Google AI Pro 年卡", "Gemini Ultra", "gemini-pro"),
    ("Google AI Ultra 20x 账号", "Gemini", "gemini-ultra-20x"),
    ("Google AI Ultra 20x 共享席位", "Gemini Pro", "gemini-ultra-20x"),
    ("Gemini 2.5 Pro 账号", "Gemini", "gemini-account"),
    ("Gemini 2.5 Pro 账号", "Google AI Pro", "gemini-account"),
    ("Gemini 1.0 Ultra 账号", "Google AI Ultra", "gemini-account"),
    ("Gemini Pro 模型访问账号", "Gemini", "gemini-account"),
    ("Gemini 1.0 Ultra 账号", "Gemini", "gemini-account"),
    ("Gemini Pro 月卡", "Gemini", "gemini-pro"),
    ("Gemini 3.1 Pro 会员", "Gemini", "gemini-subscription"),
    ("Gemini 2.5 Pro 套餐", "Google AI Pro", "gemini-subscription"),
    ("Gemini 2.5 Pro subscription", "Google AI Pro", "gemini-subscription"),
    ("Cursor Pro+ 订阅", "Cursor Pro", "cursor-pro-plus"),
    ("Cursor Pro Plus 订阅", "Cursor", "cursor-pro-plus"),
    ("Cursor Ultra 成品", "Cursor Pro", "cursor-ultra"),
    ("Cursor Premium 月卡", "Cursor Pro", "cursor-premium"),
    ("Cursor Super 月卡", "Cursor", "cursor-super"),
    ("Cursor Teams 席位", "Cursor Pro", "cursor-business"),
    ("SuperGrok Heavy 月卡", "SuperGrok", "grok-heavy"),
    ("SuperGrok 月卡", "Grok", "grok-super"),
    ("Grok Super 订阅", "Grok", "grok-plan-super"),
    ("Grok Premium 订阅", "Grok", "grok-premium"),
    ("Grok Ultra 订阅", "Grok", "grok-ultra"),
    ("ChatGPT Business 团队邀请", "ChatGPT K12", "chatgpt-business"),
    ("ChatGPT Edu 成品", "ChatGPT", "chatgpt-edu"),
    ("ChatGPT K12 团队邀请", "ChatGPT Team", "chatgpt-k12"),
])
def test_real_tier_wins_over_broad_shop_category(title, category, slug):
    assert classify_product(title, category).slug == slug


def test_free_account_is_not_promoted_by_marketing_description():
    result = classify_product("Claude Free 账号", "Claude", "本商品支持升级 Claude Max 20x 会员")
    assert result.slug == "claude-account"


def test_plain_subscription_is_not_assumed_to_be_pro():
    result = classify_product("Cursor 代充月卡", "Cursor")
    assert result.slug == "cursor-subscription"
    assert result.confidence < 80


def test_gemini_model_title_is_not_promoted_by_marketing_description():
    assert classify_product("Gemini Pro 模型访问账号", "Gemini", "本商品支持 Google AI Pro 会员功能").slug == "gemini-account"


def test_plan_registration_restores_pro_previously_hidden_by_seed():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.database import Base
    from app.models import Product
    from app.services.account_plans import ensure_account_plans

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Product(slug="chatgpt-pro", platform="OpenAI", display_name="ChatGPT Pro", is_visible=False))
        db.flush()
        ensure_account_plans(db)
        pro = db.scalar(select(Product).where(Product.slug == "chatgpt-pro"))
        assert pro.is_visible and "未注明" in pro.display_name
        max_20x = db.scalar(select(Product).where(Product.slug == "claude-pro-20x"))
        assert max_20x.display_name == "Claude Max 20x"
    engine.dispose()


@pytest.mark.parametrize("source", ["ldxp", "16688"])
@pytest.mark.parametrize(("title", "category", "description", "slug"), [
    ("【使用7天｜质保7天】Business / Team 标准席位续费码【仅限旧空间续费】", "", "不是5Xteam；可与个人 Plus 共存", "chatgpt-business"),
    ("【使用15天｜质保15天】Business / Team 标准席位激活码【仅限激活新空间】", "OpenAI Pro 20x", "本商品按15天出售", "chatgpt-business"),
    ("Perplexity Max 自助充值月卡(无积分)", "", "Perplexity Max 200刀/月（有 JPT / Claude 模型）", None),
    ("Perplexity Max月卡 200刀 iOS充值", "OpenAI Pro 20x", "支持 ChatGPT Pro 和 Claude Pro", None),
    ("Muse AI 10亿token成品号（类似于SuperGroK bot）", "成品plus区", "支持 Claude、Gemini、GPT", "muse-account"),
    ("Muse成品号+10亿token质保首登", "OpenAI Pro 5x", "价值100刀，可使用GPT模型", "muse-account"),
    ("Muse AI邀请码 10亿token免费拿（对标SuperGro-k bot）", "", "", "muse-invite"),
    ("JEV 成品账号", "OpenAI Pro 20x", "支持 GPT 和 Claude", "jev-account"),
    ("JEV 邀请码", "", "", "jev-invite"),
    ("JEV Plus 会员月卡", "GPT Plus", "", "jev-subscription"),
    ("Muse AI 手机接码", "", "", "muse-access-service"),
    ("JEV AI订阅", "", "", "jev-subscription"),
    ("ChatGPT Pro 500 会员", "OpenAI Pro 20x", "", "chatgpt-pro-500"),
    ("ChatGPT Pro $200 月卡", "OpenAI Pro 5x", "", "chatgpt-pro-200"),
    ("Codex 点数充值 250点数", "OpenAI Pro 20x", "200刀套餐也可充值", None),
    ("XG-200刀额度", "", "", None),
    ("Amusement 游戏账号", "", "", None),
    ("Jevons 教程会员", "", "", None),
    ("The X Subscription Premium 月卡", "", "", "x-subscription-premium"),
    ("X Plus 订阅", "", "", "x-subscription-plus"),
    ("X Ultra 订阅", "", "", "x-subscription-ultra"),
    ("X Premium 月卡", "", "", "x-premium"),
    ("X Premium+ 月卡", "", "", "x-premium-plus"),
    ("Grok Teams 团队套餐", "Grok Super", "", "grok-team"),
    ("Codex Pro 5X 【保订阅~智利/埃及卡冲】支持续费（不支持升级菲区20x）", "OpenAI Pro 20x", "", "chatgpt-pro-5x"),
])
def test_catalog_brand_and_plan_regressions(source, title, category, description, slug):
    result = classify_product(title, category, description, source_platform=source)
    assert result.slug == slug


@pytest.mark.parametrize("source", ["ldxp", "16688"])
def test_business_sku_duration_wins_over_shared_monthly_description(source):
    result = classify_product(
        "【使用15天｜质保15天】Business / Team 标准席位激活码【仅限激活新空间】",
        "OpenAI Pro 20x", "标准套餐一个月，全程质保", source_platform=source,
    )
    assert result.slug == "chatgpt-business"
    assert result.service_period == "fifteen_days"
    assert result.warranty == "fifteen_days"
