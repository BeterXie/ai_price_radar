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
        ("Codex 账号独享", "AI账号", "codex-access"),
        ("OpenAI Codex 手机接码", "Open Ai", "codex-access"),
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
        ("高级会员直充一个月", "Claude", "claude-account"),
    ],
)
def test_target_brand_products_are_classified(title: str, category: str, slug: str):
    assert classify_product(title, category).slug == slug


def test_stock_normalization():
    assert normalize_stock("有货", None) == "in_stock"
    assert normalize_stock("", 0) == "out_of_stock"
