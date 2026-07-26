import pytest

from common import Product, classify, ensure_products, session_for


@pytest.mark.parametrize(
    ("title", "category", "expected"),
    [
        ("Google Gmail 老号", "谷歌账号", None),
        ("小红书自动化工具月卡", "自动化工具", None),
        ("StyleMe Chrome插件 API额度", "浏览器插件", None),
        ("百度网盘 Plus 成品号", "网盘账号", None),
        ("多模型 API KEY", "GPT | Gemini | Claude | Grok", None),
        ("Codex/Claude 官方中转API 50美元", "ChatGPT", None),
        ("gm ic邮箱 Free 已开通2fa，百分百0元优惠，开plus专用", "GPT Free", None),
        ("谷歌邮箱成品老号，带2FA", "Gemini", None),
        ("ChatGPT Plus 直充一个月", "", "chatgpt-plus"),
        ("ChatGPT Free 成品号", "", "chatgpt-account"),
        ("GPT Business Team K12 自动拉", "", "chatgpt-k12"),
        ("GPT Team 团队邀请 月付", "", "chatgpt-k12"),
        ("GPT PRO 成品号（5x）无质保版", "", "chatgpt-pro-5x"),
        ("ChatGPT 5✖️Pro 一个月", "", "chatgpt-pro-5x"),
        ("ChatGPT Pro x 20 会员", "", "chatgpt-pro-20x"),
        ("GPT Pro20× 一个月", "", "chatgpt-pro-20x"),
        ("ChatGPT Pro 200刀会员", "", "chatgpt-pro"),
        ("GPT Plus 官方充值", "GPT Pro 20X 充值", "chatgpt-plus"),
        ("ChatGPT Go 正规充值", "GPT Team/Go", "chatgpt-go"),
        ("一个月 GPT Go会员 美区订阅", "GPT Team/Go", "chatgpt-go"),
        ("全新微软邮箱，已注册好ChatGPT（不含plus）", "GPT Free", "chatgpt-account"),
        ("Chatgpt普通账号", "GPT Free", "chatgpt-account"),
        ("gpt free（免费账号）iCloud邮箱", "GPT Free", "chatgpt-account"),
        ("GPT PLUS镜像站(天卡)", "GPT", None),
        ("ChatGPT Plus土区稳定订阅保姆级教程", "教程", None),
        ("GPT-Plus授权神器 自动化授权+接码+CPA文件生成", "AI工具", None),
        ("UPI PLUS批量提链CDK", "GPT PLUS 提链", "chatgpt-access-service"),
        ("GPT-Plus印度UPI扫码对接（CDK）", "GPT", "chatgpt-access-service"),
        ("GPT Cyber认证【Persona认证】", "GPT 直充", "chatgpt-access-service"),
        ("1个月 gpt PULS会员 IOS订阅", "GPT官方充值", "chatgpt-plus"),
        ("plsu 成品", "GPT", "chatgpt-plus"),
        ("100刀额度", "ChatGPT", None),
        ("plus成品号", "chat plus 成品号", "chatgpt-plus"),
        ("谷歌邮件 成品 Plus", "全部", "chatgpt-plus"),
        ("Codex 账号独享", "AI账号", "codex-access"),
        ("OpenAI Codex 手机接码", "Open Ai", "codex-access"),
        ("GPT-Plus-成品，需要使用CODEX自行绑定手机", "GPT", "chatgpt-plus"),
        ("Gmail GPT Free 已开2fa，开plus专用", "GPT Free", "chatgpt-access-service"),
        ("GPT PLUS 接码 全球多地区", "接码", "chatgpt-access-service"),
        ("Claude 基础账号", "AI账号", "claude-account"),
        ("Claude注册 实体手机号接码（codex接码另拍）", "Claude", "claude-account"),
        ("Claude-Kiro API KEY 100M Token", "GPT | Gemini | Claude | Grok", "claude-api-access"),
        ("Gemini 成品号", "AI账号", "gemini-account"),
        ("SuperGrok 代充值", "AI会员", "grok-super"),
        ("Grok Super 正规充值", "AI会员", "grok-super"),
        ("X（Twitter） Premium会员直充卡密", "Grok", "x-premium"),
        ("X Premium Basic 一个月官方直充", "AI会员", "x-premium-basic"),
        ("X Premium+ 12个月官方直充", "Grok 充值", "x-premium-plus"),
        ("Twitter Blue 月卡", "社交会员", "x-premium"),
        ("X Premium 12个月，包含同时长 SuperGrok", "Grok 充值", "x-premium"),
        ("SuperGrok 年卡，附赠 X Premium+", "Grok", "grok-super"),
        ("Twitter 普通账号", "社交账号", None),
        ("X Premium Business 企业认证", "企业服务", None),
        ("高级会员直充一个月", "Claude", "claude-account"),
    ],
)
def test_classifier_requires_a_target_brand(title: str, category: str, expected: str | None):
    assert classify(title, category).slug == expected


def test_description_is_only_used_for_tags_and_risks():
    result = classify("高级会员月卡", "效率工具", {"description": "支持 ChatGPT，售出不退"})
    assert result.slug is None
    assert "限制退款" in result.risks


def test_description_can_refine_an_already_identified_openai_product():
    result = classify("ChatGPT 独享账号", "OpenAI", {"description": "Business Team 自动拉入"})
    assert result.slug == "chatgpt-k12"


def test_product_catalog_groups_openai_and_retires_legacy_team_product():
    db = session_for("sqlite+pysqlite:///:memory:")
    try:
        legacy = Product(
            slug="chatgpt-team-business",
            platform="ChatGPT",
            display_name="ChatGPT Team / Business",
        )
        db.add(legacy)
        db.flush()
        products = ensure_products(db)
        assert products["chatgpt-k12"].platform == "OpenAI"
        assert products["chatgpt-pro-5x"].display_name == "ChatGPT Pro 5x"
        assert products["chatgpt-pro-20x"].display_name == "ChatGPT Pro 20x"
        assert products["codex-access"].platform == "OpenAI"
        assert products["x-premium-basic"].platform == "X"
        assert products["x-premium-plus"].display_name == "X Premium+"
        assert legacy.is_visible is False
    finally:
        db.close()


def test_plus_does_not_inherit_k12_tags_from_description():
    result = classify("ChatGPT Plus 成品号", "GPT", {"description": "支持 Team、Business 和 K12"})
    assert result.slug == "chatgpt-plus"
    assert not ({"Team", "Business", "K12"} & set(result.tags))


@pytest.mark.parametrize(
    ("title", "category", "slug", "delivery_type", "comparable"),
    [
        ("美区成品号，带接码链接，不是Plus", "GPT-plus半成品号", "chatgpt-account", "finished_account", True),
        ("ChatGPT Plus号池标准套餐", "GPT Plus", "chatgpt-plus", "shared_pool", False),
        ("ChatGPT Plus体验版日抛", "GPT Plus", "chatgpt-plus", "trial_account", False),
        ("ChatGPT Plus官方直充一个月", "GPT Plus", "chatgpt-plus", "subscription_recharge", True),
        ("ChatGPT Plus半成品未接码", "GPT Plus", "chatgpt-plus", "semi_finished_account", True),
        ("Codex中转站 API额度", "GPT-plus", None, "relay_api", False),
    ],
)
def test_delivery_form_controls_comparability(title: str, category: str, slug: str | None, delivery_type: str, comparable: bool):
    result = classify(title, category)
    assert result.slug == slug
    assert result.delivery_type == delivery_type
    assert result.is_comparable is comparable


def test_decision_facts_and_fingerprint_are_stable_across_date_prefixes():
    first = classify("7.26 ChatGPT Plus 成品号", "GPT", {"description": "月卡，质保首登，支持网页和 Codex"})
    second = classify("7/27 ChatGPT Plus 成品号", "GPT", {"description": "月卡 质保首登 支持网页和 Codex"})
    assert first.service_period == "one_month"
    assert first.warranty == "first_login"
    assert first.use_scenarios == ["web", "codex"]
    assert first.item_fingerprint == second.item_fingerprint


@pytest.mark.parametrize(
    ("title", "period"),
    [
        ("X Premium 3个月官方直充", "three_months"),
        ("X Premium 六个月全程质保", "six_months"),
        ("X Premium+ 12个月官方直充", "one_year"),
    ],
)
def test_x_premium_service_periods(title: str, period: str):
    assert classify(title).service_period == period


def test_title_period_wins_over_fulfillment_time_in_description():
    result = classify("X Premium 3个月官方直充", "Grok 充值", {"description": "下单后24小时内发货"})
    assert result.service_period == "three_months"
    unspecified = classify("X（Twitter） Premium会员直充卡密", "Grok", {"description": "24小时内发货"})
    assert unspecified.service_period == "unknown"


def test_title_warranty_wins_over_narrower_description_exclusions():
    result = classify("X Premium 3个月全程质保订阅", "Grok", {"description": "封号无质保，其他情况质保到期"})
    assert result.warranty == "subscription_term"
