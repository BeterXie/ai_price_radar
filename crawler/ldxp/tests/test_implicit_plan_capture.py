from __future__ import annotations

import pytest

from ldxp_crawler.browser_scanner import BrowserShopScanner


@pytest.mark.parametrize("title,category", [
    ("Plus | 已接马", "Plus成品(质保首登）"),
    ("【质保28天】G plus 稳定号", "Plus成品(保20-30天）"),
    ("iCloud 成品 Plus（质保首登）- UPI", "全部"),
    ("菲区Plus直充渠道1-质保订阅", "Go与Plus直充"),
    ("1个月Plus半价资格号[只是资格不是成品]", "Plus半价直充/成品"),
    ("Pro10x | 质保7天订阅", "Pro直充与成品"),
    ("美区IOS Pro20x正规直充", "Pro直充与成品"),
    ("菲区 Pro50x 正规直充", "Pro直充与成品"),
    ("菲区GO正规充值-质保订阅", "Go与Plus直充"),
    ("Team 5x 长效车｜发账密2fa｜gmail邮箱", "Codex Team"),
    ("Team10X｜过夜头车｜Gmail邮箱", "Codex Team"),
    ("三轮 5x team 22点踢 谷歌邮箱 给账号密码", "Codex Team"),
    ("X（Twitter） Premium会员直充卡密", "全部"),
    ("【10Xteam 首车账密2fa 18号8点30踢】质保1小时", "team"),
    ("Team 真头车｜不踢人｜500~1000刀10X额度", "team"),
    ("Team 1x｜长效包月(含周限)｜拼车｜全程质保", "team"),
    ("Team 5x｜三车过夜｜早9点踢｜2fa-G邮箱｜质保首登1H", "team"),
    ("G free 【已接马】gmail邮箱 支持401批量找回 2fa", "codex free"),
    ("【iCloud注册的接马free】可以邮箱收件，RT号，账号-密码-2fa", "free"),
    ("【高质量-已接马】free家宽gmail谷歌注册-账密2fa-可用5xteam车子号", "Gmail邮箱"),
    ("【质保28天】G plus 稳定号质保28天【日本实卡渠道】", "G【质保专区】"),
    ("【菲区自动卡充】 Plus 质保30天 (卡密不可囤)", "G【质保专区】"),
    ("全业务长效接马【25-30天】【美国ATT运营商实卡】", "Codex 手机接马"),
])
def test_implicit_plans_survive_brand_and_keyword_filters(title, category):
    scanner = object.__new__(BrowserShopScanner)
    row = {"goods_key": "sku", "name": title, "category": {"name": category},
           "price": 28.5, "extend": {"stock_count": 3}}
    matches = scanner._build_matches([row], ["gpt", "claude"], "https://wzyp.cn/shop/TEST", False)
    assert len(matches) == 1
    assert matches[0].product_key == "sku"
    assert matches[0].listed_price == 28.5
    assert matches[0].stock_count == 3
    assert matches[0].raw == row
    assert matches[0].matched_keywords


@pytest.mark.parametrize("title,category", [
    ("百度网盘 Plus 成品号", "网盘账号"),
    ("Plus 独享会员", "YouTube"),
    ("Google Gmail 老号", "Codex Team"),
    ("谷歌邮箱成品老号，带2FA", "Gemini"),
    ("gm ic邮箱 Free 已开通2fa，百分百0元优惠，开plus专用", "GPT Free"),
    ("Team Gmail 企业邮箱账号", "邮箱"),
    ("Pro 正版月卡", "设计软件"),
    ("Go 会员充值", "游戏"),
    ("Telegram Premium 三个月订阅", "Muse"),
    ("Team Gmail 企业邮箱账号", "team"),
    ("Microsoft Teams 企业账号", "team"),
])
def test_generic_email_and_unrelated_memberships_stay_excluded(title, category):
    scanner = object.__new__(BrowserShopScanner)
    row = {"goods_key": "unrelated", "name": title, "category": {"name": category},
           "description": "也可注册 ChatGPT、Claude"}
    assert scanner._build_matches([row], ["账号", "会员", "plus"], "https://wzyp.cn/shop/TEST", False) == []
