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
