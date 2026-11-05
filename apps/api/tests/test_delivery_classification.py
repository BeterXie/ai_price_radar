import pytest

from app.services.classifier import classify_product


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Claude Max 20x 成品号，美区，已过KYC，iOS充值", "", "finished_account"),
        ("G PLUS 成品号（不是充值），质保25天不掉订阅", "", "finished_account"),
        ("Claude Pro 高质量成品号 质保订阅", "", "finished_account"),
        ("Gemini Ultra 成品账号 官方订阅一年", "", "finished_account"),
        ("SuperGrok 成品号 卡充订阅一个月", "", "finished_account"),
        ("ChatGPT Plus 半成品账号 订阅一个月", "", "semi_finished_account"),
        ("ChatGPT Plus 自有账号代充 一个月", "", "subscription_recharge"),
        ("Claude Pro 账号充值", "", "subscription_recharge"),
        ("Claude Pro 代充，需提供账号密码", "", "subscription_recharge"),
        ("ChatGPT Plus 订阅", "无需提供账号密码，自助充值", "subscription_recharge"),
        ("Gemini Ultra 官充 月卡 质保订阅", "", "subscription_recharge"),
        ("SuperGrok 官方订阅", "", "unknown"),
        ("ChatGPT Plus 订阅一个月", "账号密码交付，已开通会员", "finished_account"),
        ("ChatGPT Plus 订阅一个月", "为您的账号充值会员", "subscription_recharge"),
        ("ChatGPT Plus 自有账号订阅", "", "unknown"),
        ("Claude Max 20x 正规代充/成品+50", "提供代充或成品账号", "unknown"),
        ("Cursor Pro 在线充值/成品", "", "unknown"),
        ("Claude Max 20x 成品号可代充", "", "unknown"),
        ("ChatGPT Plus 成品号", "非共享账号，禁止多人共享，禁止反代", "finished_account"),
        ("ChatGPT Plus 成品号", "稳定程度远超老号，绝非日抛账号", "finished_account"),
        ("ChatGPT Plus 成品号", "避免频繁切换 IP、多人共享账号或多设备混用。", "finished_account"),
        ("ChatGPT Plus 官方直充", "多人共享、频繁切换环境等行为可能触发官方风控。", "subscription_recharge"),
        ("ChatGPT Pro 200 订阅", "Pro充值卡密，不用账号密码。请退出team，否则充值失败。", "subscription_recharge"),
        ("ChatGPT Plus 订阅", "成品账号，非共享账号", "finished_account"),
        ("ChatGPT Plus 成品号", "发货格式是 免费版账号+充值卡密，需要您自助完成充值后使用", "semi_finished_account"),
        ("Codex 接码服务", "收不到码会自动释放手机号回号池", "verification_service"),
        ("ChatGPT Plus 成品号", "多人共享账号，随机分配", "shared_pool"),
        ("ChatGPT Plus 订阅", "中转非成品号，发货商品为兑换码", "relay_api"),
        ("GPT Pro 100刀自助卡密 5x 质保订阅", "", "card_code"),
        ("Gemini AI Pro 领取链接", "非共享账号，使用自己的 Google 账号领取", "card_code"),
        ("ChatGPT 普号", "", "finished_account"),
        ("Claude Pro 官网代充", "非共享、非镜像。❌ 多人共享同一账号。封号情况与多人共享等因素有关。", "subscription_recharge"),
        ("ChatGPT Plus 成品号", "<p>非<strong>0元试用号</strong>，全程质保</p>", "finished_account"),
        ("ChatGPT Plus 成品号", "多人共享不在售后保障范围内。发现反代不保。", "finished_account"),
        ("Codex Go 官方充值", "因中转、反代或违反使用条款导致封号不予质保。", "subscription_recharge"),
        ("Grok 成品号", "想省事可直接看反代软件（本店另有）。", "finished_account"),
        ("X Cursor 月卡", "卡密自助充值，充值至您自己的账号，不包含额外 API 额度。", "subscription_recharge"),
        ("ChatGPT Plus 会员", "下单后收到：账号 | 密码 | 2fa。未接马，使用 Codex 时需手机验证。", "semi_finished_account"),
        ("ChatGPT Plus 官充", "0元试用号可以支付。官方代充，正规卡代付。", "subscription_recharge"),
        ("Claude KYC 认证服务", "提供您账号的认证链接", "verification_service"),
        ("Gemini Plus 激活链接", "", "card_code"),
        ("Grok 三人车", "不是中转api", "shared_pool"),
        ("Claude Pro 成品号 免KYC认证", "", "finished_account"),
        ("ChatGPT Plus 已接马成品号 免手机号验证", "", "finished_account"),
        ("Gemini Ultra 官网直冲", "非家庭组共享，也不是家庭组车位，充值至自己的账号", "subscription_recharge"),
        ("ChatGPT Plus 成品号", "不是0元试用的日抛号，非低质量日抛号", "finished_account"),
        ("ChatGPT Pro 成品号", "号池接入订单号，自动发货到邮箱。发货格式：邮箱----密码----2fa", "finished_account"),
        ("ChatGPT Plus 仅反代无账密", "codex需要反代使用，本地安装工具", "session_token"),
        ("ChatGPT Business 母号双席位代充", "", "subscription_recharge"),
        ("Claude KYC 认证普号 outlook邮箱", "", "finished_account"),
        ("Claude KYC 代认证", "联系客服处理认证", "verification_service"),
        ("ChatGPT Plus 未接马", "可网页可反代", "semi_finished_account"),
        ("Codex Team 车位", "正规团队车位，可与 Plus 并存", "team_seat"),
        ("Gemini 家庭组席位拼车", "", "shared_pool"),
    ],
)
def test_delivery_follows_what_is_supplied(title, description, expected):
    result = classify_product(title, description=description)
    assert result.delivery_type == expected
    if expected in {"unknown", "shared_pool", "relay_api"}:
        assert not result.is_comparable
