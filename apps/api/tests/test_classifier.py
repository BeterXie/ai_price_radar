import pytest

from app.services.classifier import classify_product, normalize_stock


def test_team_classification():
    result = classify_product("GPT Business Team K12 自动拉 无质保")
    assert result.slug == "chatgpt-k12"
    assert "K12" in result.tags
    assert "无质保" in result.risk_flags


def test_plus_excludes_api():
    result = classify_product("ChatGPT Plus 直充一个月")
    assert result.slug == "chatgpt-plus"
    assert "直充" in result.tags


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("GP.T Plus 菲区 CDK", "chatgpt-plus"),
        ("GTP Pro 5x 菲区充值", "chatgpt-pro-5x"),
        ("PRO 20X 官方充值月卡", "chatgpt-pro-20x"),
        ("G Pro X20 官方充值月卡", "chatgpt-pro-20x"),
        ("G Plus 官方充值", "chatgpt-plus"),
        ("Gro Heavy 速刷成品号", "grok-super"),
        ("Supergro 30刀月卡", "grok-super"),
        ("Gro-free 普号", "grok-account"),
    ],
)
def test_16688_aliases_are_platform_specific(title: str, slug: str):
    assert classify_product(title, source_platform="16688").slug == slug
    assert classify_product(title).slug is None


@pytest.mark.parametrize(
    ("title", "category", "expected"),
    [
        ("GP.T Plus 使用指南", "", None),
        ("G Plus 镜像站", "", None),
        ("G Plus API额度", "", "openai-api-credit"),
        ("Gmail API额度", "", None),
        ("百度网盘 API额度", "", None),
        ("API额度", "Gmail", None),
        ("API额度", "百度网盘", None),
        ("G Plus 成品号 附使用教程", "", "chatgpt-plus"),
    ],
)
def test_16688_aliases_reject_non_products_and_preserve_api_classification(title: str, category: str, expected: str | None):
    assert classify_product(title, category, source_platform="16688").slug == expected


def test_16688_alias_can_use_description_context():
    result = classify_product(
        "官方充值 Plus CDK",
        "AI与效率",
        "商品内容：GP.T Plus 1个月，官方订阅充值",
        source_platform="16688",
    )
    assert result.slug == "chatgpt-plus"


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("ChatGPT Free 成品号", "chatgpt-account"),
        ("GPT Team 团队邀请 月付", "chatgpt-k12"),
        ("ChatGPT K12 自动拉", "chatgpt-k12"),
        ("GPT PRO 成品号（5x）无质保版", "chatgpt-pro-5x"),
        ("ChatGPT 5✖️Pro 一个月", "chatgpt-pro-5x"),
        ("ChatGPT Pro x 20 会员", "chatgpt-pro-20x"),
        ("GPT Pro20× 一个月", "chatgpt-pro-20x"),
        ("ChatGPT Pro 200刀会员", "chatgpt-pro"),
        ("GPT Plus 官方充值", "chatgpt-plus"),
        ("ChatGPT Go 正规充值", "chatgpt-go"),
        ("一个月 GPT Go会员 美区订阅", "chatgpt-go"),
    ],
)
def test_openai_mainstream_tiers_are_distinct(title: str, slug: str):
    assert classify_product(title).slug == slug


def test_explicit_title_tier_wins_over_a_wrong_source_category():
    result = classify_product("GPT Plus 官方充值", "GPT Pro 20X 充值", "Pro 20x 专区")
    assert result.slug == "chatgpt-plus"


def test_go_title_is_not_swallowed_by_a_combined_team_category():
    result = classify_product("ChatGPT Go 正规充值", "GPT Team/Go")
    assert result.slug == "chatgpt-go"


@pytest.mark.parametrize(
    ("title", "category", "slug"),
    [
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
    ],
)
def test_plus_catalog_rejects_free_and_non_subscription_items(title: str, category: str, slug: str | None):
    assert classify_product(title, category).slug == slug


def test_plus_does_not_inherit_tier_tags_from_description():
    result = classify_product("ChatGPT Plus 成品号", "GPT", "支持 Team、Business 和 K12")
    assert result.slug == "chatgpt-plus"
    assert not ({"Team", "Business", "K12"} & set(result.tags))


def test_openai_description_can_refine_an_already_identified_product():
    result = classify_product("ChatGPT 独享账号", "OpenAI", "Business Team 自动拉入")
    assert result.slug == "chatgpt-k12"


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Google Gmail 老号", "谷歌账号"),
        ("自用订阅链接30天60G", "网络加速"),
        ("小红书自动化工具月卡", "自动化工具"),
        ("StyleMe Chrome插件 API额度", "浏览器插件"),
        ("百度网盘 Plus 成品号", "网盘账号"),
        ("多模型 API KEY", "GPT | Gemini | Claude | Grok"),
        ("Codex/Claude 官方中转API 50美元", "ChatGPT"),
        ("gm ic邮箱 Free 已开通2fa，百分百0元优惠，开plus专用", "GPT Free"),
        ("谷歌邮箱成品老号，带2FA", "Gemini"),
        ("Twitter 普通账号", "社交账号"),
        ("X Premium Business 企业认证", "企业服务"),
    ],
)
def test_unrelated_products_are_not_classified(title: str, category: str):
    assert classify_product(title, category).slug is None


def test_description_cannot_supply_missing_brand_context():
    result = classify_product("高级会员月卡", "效率工具", "支持 ChatGPT，售出不退")
    assert result.slug is None
    assert "限制退款" in result.risk_flags


@pytest.mark.parametrize(
    ("title", "category", "slug"),
    [
        ("plus成品号", "chat plus 成品号", "chatgpt-plus"),
        ("谷歌邮件 成品 Plus", "Open Ai", "chatgpt-plus"),
        ("谷歌邮件 成品 Plus", "全部", "chatgpt-plus"),
        ("Codex 账号独享", "AI账号", "chatgpt-plus"),
        ("OpenAI Codex 手机接码", "Open Ai", "chatgpt-access-service"),
        ("【源头】8.31🚀新 codex plus账号 已接马【带rt】，sub2 CPA格式", "", "chatgpt-plus"),
        ("Go菲区CDK｜官方充值｜1个月｜质保订阅30天", "Codex", "chatgpt-go"),
        ("Codex Go 1个月【质保30天】【自动卡充】", "", "chatgpt-go"),
        ("GPT free账号【已接码】codex(50起)", "", "chatgpt-account"),
        ("codex接码|美国实卡一次性接码|可无限自助换号", "", "chatgpt-access-service"),
        ("GPT-Plus-成品，需要使用CODEX自行绑定手机", "GPT", "chatgpt-plus"),
        ("Gmail GPT Free 已开2fa，开plus专用", "GPT Free", "chatgpt-access-service"),
        ("GPT PLUS 接码 全球多地区", "接码", "chatgpt-access-service"),
        ("Claude 基础账号", "AI账号", "claude-account"),
        ("Claude注册 实体手机号接码（codex接码另拍）", "Claude", "claude-account"),
        ("Claude Pro 一个月", "AI会员", "claude-pro"),
        ("Claude-Kiro API KEY 100M Token", "GPT | Gemini | Claude | Grok", "claude-api-access"),
        ("Gemini 成品号", "AI账号", "gemini-account"),
        ("Google One AI 一个月", "AI会员", "gemini-advanced"),
        ("Gemini API KEY", "AI接口", "gemini-api-access"),
        ("SuperGrok 代充值", "AI会员", "grok-super"),
        ("Grok Super 正规充值", "AI会员", "grok-super"),
        ("Grok 成品号", "AI账号", "grok-account"),
        ("Grok API Token", "AI接口", "grok-api-access"),
        ("X（Twitter） Premium会员直充卡密", "Grok", "x-premium"),
        ("X Premium Basic 一个月官方直充", "AI会员", "x-premium-basic"),
        ("X Premium+ 12个月官方直充", "Grok 充值", "x-premium-plus"),
        ("Twitter Blue 月卡", "社交会员", "x-premium"),
        ("X Premium 12个月，包含同时长 SuperGrok", "Grok 充值", "x-premium"),
        ("SuperGrok 年卡，附赠 X Premium+", "Grok", "grok-super"),
        ("高级会员直充一个月", "Claude", "claude-account"),
    ],
)
def test_target_brand_products_are_classified(title: str, category: str, slug: str):
    assert classify_product(title, category).slug == slug


def test_stock_normalization():
    assert normalize_stock("有货", None) == "in_stock"
    assert normalize_stock("", 0) == "out_of_stock"


@pytest.mark.parametrize(
    ("title", "category", "slug", "delivery_type", "comparable"),
    [
        ("美区成品号，带接码链接，不是Plus", "GPT-plus半成品号", "chatgpt-account", "finished_account", True),
        ("ChatGPT Plus号池标准套餐", "GPT Plus", "chatgpt-plus", "shared_pool", False),
        ("ChatGPT Plus体验版日抛", "GPT Plus", "chatgpt-plus", "trial_account", False),
        ("ChatGPT Plus官方直充一个月", "GPT Plus", "chatgpt-plus", "subscription_recharge", True),
        ("ChatGPT Plus半成品未接码", "GPT Plus", "chatgpt-plus", "semi_finished_account", True),
        ("Codex中转站 API额度", "GPT-plus", None, "relay_api", False),
        ("GPT Team团队邀请车位", "GPT Team", "chatgpt-k12", "team_seat", True),
    ],
)
def test_delivery_form_controls_comparability(title: str, category: str, slug: str | None, delivery_type: str, comparable: bool):
    result = classify_product(title, category)
    assert result.slug == slug
    assert result.delivery_type == delivery_type
    assert result.is_comparable is comparable


def test_decision_facts_and_fingerprint_are_stable_across_date_prefixes():
    first = classify_product("7.26 ChatGPT Plus 成品号", "GPT", "月卡，质保首登，支持网页和 Codex")
    second = classify_product("7/27 ChatGPT Plus 成品号", "GPT", "月卡 质保首登 支持网页和 Codex")
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
    assert classify_product(title).service_period == period


def test_title_period_wins_over_fulfillment_time_in_description():
    result = classify_product("X Premium 3个月官方直充", "Grok 充值", "下单后24小时内发货")
    assert result.service_period == "three_months"
    unspecified = classify_product("X（Twitter） Premium会员直充卡密", "Grok", "24小时内发货")
    assert unspecified.service_period == "unknown"


def test_title_warranty_wins_over_narrower_description_exclusions():
    result = classify_product("X Premium 3个月全程质保订阅", "Grok", "封号无质保，其他情况质保到期")
    assert result.warranty == "subscription_term"


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Nume API 10$ plus分组 0.07", "GPT-plus半成品号"),
        ("纯plus-G(cx,5,4)—100刀", "GPT-plus半成品号"),
        ("纯plus-G(cx,5,4)—10刀", "GPT-plus半成品号"),
        ("纯plus-G(cx,5,4)—200刀", "GPT-plus半成品号"),
        ("纯plus-G(cx,5,4)—10刀", "codex中转站"),
        ("纯plus-G(cx,5,4)—100刀", "codex中转站"),
        ("纯plus-G(cx,5,4)—200刀", "codex中转站"),
        ("GPTplus中转300刀", "GPT-plus半成品号"),
        ("GPTplus50刀", "GPT-plus半成品号"),
        ("plus10刀不限时，看好说明再买", "GPT-plus半成品号"),
        ("plus20刀不限时，看好说明再购买", "GPT-plus半成品号"),
        ("10刀不限时 PLUS/PRO号池", "GPT-plus半成品号"),
    ],
)
def test_relay_groups_and_non_20_dollar_quotas_rejected_from_plus(title: str, category: str):
    result = classify_product(title, category)
    assert result.slug is None, f"{title} in {category} should not classify into {result.slug}"


@pytest.mark.parametrize(
    ("title", "category", "description", "expected_slug", "expected_delivery", "expected_comparable"),
    [
        ("支付宝原价订阅ChatGPT Plus，保姆教程持续更新....", "Gpt", "", None, "unknown", False),
        ("内部教程_Gemini3.1Pro如何开启家庭组？（仅图文教程，不含其他使用指导）", "教程", "", None, "unknown", False),
        ("低价GPT接码渠道Plus接码渠道Codex接码渠道Plus成品号接码渠道", "GPT-plus半成品号", "", None, "unknown", False),
        ("plus pro邀请额度增加 自行使用卖出无售后", "OpenAI 额度充值", "", None, "unknown", False),
        ("【测试商品】不是 GPT PLUS RT号，不要购买", "Gemini", "", None, "unknown", False),
        ("VISA 0刀虚拟卡 485954(Gemini KIRO GPT PAYPAL用不了拍错不退） 有效期两小时", "0刀卡和一刀卡", "", None, "unknown", False),
        ("plus已接码有rt，无账号和密码，仅支持反代！不会用反代软件的切勿下单！", "gpt", "", "chatgpt-plus", "session_token", False),
        ("自营2- Plus 成品号 已接码 只能反代 json发货 没有账号密码那些", "全部", "只可反代，没有账号密码", "chatgpt-plus", "session_token", False),
        ("OpenAI Pro 20X 额度｜50美金｜OpenAI 5.6-sol｜ OpenAI image2", "20X(无质保)", "", None, "api_credit", False),
        ("G Team bug 子号 最低200刀（无质保，拿着卡密去兑换地址下载JSON文件）", "OpenAI Team/Go", "", "chatgpt-k12", "team_seat", True),
        ("长效 周额team", "ChatGPT福利号", "", "chatgpt-k12", "team_seat", True),
        ("plus成品号30天10人拼车】plus订阅拼车30天 全程质保🔥", "GPT Plus", "", "chatgpt-plus", "shared_pool", False),
        ("G plus会员拼车号【随机1-4人用】", "GPT Plus", "", "chatgpt-plus", "shared_pool", False),
        ("【质保稳定30天，3人共享账号】", "GPT Plus", "", "chatgpt-plus", "shared_pool", False),
        ("Super Grok官方正规充值1个月（质保30天订阅）", "Grok分组", "", "grok-super", "subscription_recharge", True),
        ("GrokSuper代充值（1个月）", "Grok分组", "", "grok-super", "subscription_recharge", True),
        ("【特惠秒发】独享个人月度会员 官方正规实卡开通", "通用AI", "本商品为 ChatGPT Plus 官方正规独享号，带完整邮箱密码和2FA", "chatgpt-plus", "finished_account", True),
        ("【直充秒发】独立个人订阅 月付质保", "海外会员", "本商品为 Claude Pro 个人会员代充，正规信用卡开通", "claude-pro", "subscription_recharge", True),
        ("【年付特惠】高级版会员 质保一年", "热门AI", "Google Gemini Advanced 1年会员直充，享受2TB空间及最新AI模型", "gemini-advanced", "subscription_recharge", True),
    ],
)
def test_detail_description_and_robust_exclusions(
    title: str,
    category: str,
    description: str,
    expected_slug: str | None,
    expected_delivery: str,
    expected_comparable: bool,
):
    result = classify_product(title, category, description)
    assert result.slug == expected_slug, f"Slug mismatch for '{title}': got {result.slug}"
    assert result.is_comparable is expected_comparable, f"Comparable mismatch for '{title}'"
    if expected_slug is not None:
        assert result.delivery_type == expected_delivery, f"Delivery mismatch for '{title}': got {result.delivery_type}"


