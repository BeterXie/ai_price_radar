from __future__ import annotations

import pytest

from ldxp_crawler.browser_scanner import BrowserShopScanner, has_target_brand
from ldxp_crawler.models import ShopScanResult
from ldxp_gpt_crawler import intake_result_payload


@pytest.mark.parametrize("keywords", [["gpt", "muse"], ["gpt"]])
def test_muse_shop_products_validate_without_unrelated_memberships(keywords):
    scanner = object.__new__(BrowserShopScanner)
    rows = [
        {"goods_key": "muse-310", "name": "【质保成品】Muse310亿 一卡一绑 带微软邮箱", "price": 39.8, "extend": {"stock_count": 3}},
        {"goods_key": "telegram", "name": "TG Premium 三个月订阅【人工发货】", "price": 100},
        {"goods_key": "muse-10", "name": "【质保成品】Muse10亿 一卡一绑 带微软邮箱", "price": 20, "extend": {"stock_count": 47}},
        {"goods_key": "muse-invite", "name": "muse邀请助力（满十单优惠）", "price": 0.8, "extend": {"stock_count": 52}},
    ]
    for row in rows:
        row["category"] = {"name": "muse"}
    matches = scanner._build_matches(rows, keywords, "https://wzyp.cn/shop/TESTMUSE", False)

    assert [item.product_key for item in matches] == ["muse-310", "muse-10", "muse-invite"]
    assert [item.listed_price for item in matches] == [39.8, 20, 0.8]
    assert [item.stock_count for item in matches] == [3, 47, 52]
    result = ShopScanResult(token="TESTMUSE", status="success", matches=matches)
    assert intake_result_payload(result) == ("validated", 3, "")


def test_muse_category_accepts_generic_accounts_but_not_other_memberships():
    assert has_target_brand("独享账号", "Muse AI")
    assert has_target_brand("MUSE.AI 邀请码")
    assert not has_target_brand("Telegram Premium 三个月订阅", "Muse")
    assert not has_target_brand("电报会员订阅", "Muse")
    assert not has_target_brand("谷歌邮箱成品老号，带2FA", "Muse")
