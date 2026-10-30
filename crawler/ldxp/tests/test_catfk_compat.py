from __future__ import annotations

import hashlib
import json
import logging
from unittest.mock import MagicMock

import pytest

from ldxp_crawler.browser_scanner import (
    BrowserShopScanner,
    CaptureState,
    GOODS_ENDPOINT,
    INFO_ENDPOINT,
    RequestTemplate,
)
from ldxp_crawler.db import StateDB
from ldxp_crawler.discovery import Discovery
from ldxp_crawler.utils import extract_shop_identity, extract_shop_token, extract_shop_urls, normalize_shop_url
from ldxp_gpt_crawler import intake_claim_token, intake_result_payload


CATFK_URL = "https://catfk.com/shop/I8WO6J9O"
OFFICIAL_URL = "https://wzyp.cn/shop/I8WO6J9O"


def scanner_for(tmp_path):
    return BrowserShopScanner(
        profile_dir=tmp_path / "profile",
        storage_state_path=tmp_path / "state.json",
        executable_path=None,
        headless=True,
        timeout=5,
        page_wait=0,
        manual_challenge_seconds=0,
        max_pages=3,
        page_size=1,
        fetch_mode="all",
        request_interval=0,
        logger=logging.getLogger("catfk-test"),
    )


@pytest.mark.parametrize("url", [CATFK_URL, "catfk.com/shop/I8WO6J9O", "//catfk.com/shop/I8WO6J9O"])
def test_catfk_normalization_keeps_origin_and_separates_api_token(url):
    assert normalize_shop_url(url) == CATFK_URL
    assert extract_shop_urls(url) == [CATFK_URL]
    assert extract_shop_token(url) == "I8WO6J9O"
    assert extract_shop_identity(url) == "catfk:I8WO6J9O"
    assert intake_claim_token(url) == "catfk:I8WO6J9O"
    assert intake_claim_token(OFFICIAL_URL) == "I8WO6J9O"


def test_long_catfk_identity_stays_within_storage_limit():
    raw_token = "A" * 128
    expected = "catfk:sha256:" + hashlib.sha256(raw_token.casefold().encode()).hexdigest()
    assert extract_shop_identity(f"https://catfk.com/shop/{raw_token}") == expected
    assert extract_shop_identity(f"https://catfk.com/shop/{raw_token.lower()}") == expected
    assert len(expected) <= 128
    boundary = "A" * 122
    assert extract_shop_identity(f"https://catfk.com/shop/{boundary}") == f"catfk:{boundary}"


def scan_fixture(scanner, source_url):
    page = MagicMock()
    page.url = source_url
    page.goto.return_value.status = 200
    calls = []

    def evaluate(_script, args):
        calls.append(args)
        if args["url"].endswith(INFO_ENDPOINT):
            document = {"code": 1, "data": {"nickname": "Fixture shop", "link": OFFICIAL_URL}}
        else:
            assert args["url"].endswith(GOODS_ENDPOINT)
            current = args["payload"]["current"]
            document = {"code": 1, "data": {"total": 2, "list": [{
                "goods_key": f"KEY{current}",
                "name": f"ChatGPT Plus {current}",
                "price": "29.90",
                "market_price": "39.90",
                "category": {"name": "ChatGPT"},
                "extend": {"stock_count": 3, "send_order": 0},
                "link": "https://wzyp.cn/item/KEY1" if current == 1 else "/item/KEY2",
            }]}}
        return {"status": 200, "text": json.dumps(document)}

    page.evaluate.side_effect = evaluate
    scanner._new_page_with_capture = lambda: (page, CaptureState())
    scanner._is_challenge = lambda _page: False
    scanner._body_text = lambda _page: ""
    scanner._dom_products = lambda _page: []
    scanner.save_state = lambda: None
    result = scanner.scan_shop({"token": intake_claim_token(source_url), "url": source_url}, ["gpt"])
    return result, calls, page


def test_catfk_scan_preserves_identity_origin_and_paginates_with_upstream_token(tmp_path):
    result, calls, page = scan_fixture(scanner_for(tmp_path), CATFK_URL)
    page.goto.assert_called_once_with(CATFK_URL, wait_until="domcontentloaded")
    assert result.status == "success"
    assert result.token == "catfk:I8WO6J9O"
    assert result.shop_url == CATFK_URL
    assert result.api_host == "catfk.com"
    assert result.scanned_item_count == len(result.matches) == 2
    assert all(call["payload"]["token"] == "I8WO6J9O" for call in calls)
    assert all(call["url"].startswith("https://catfk.com/shopApi/Shop/") for call in calls)
    assert [match.product_key for match in result.matches] == ["KEY1", "KEY2"]
    assert [match.product_url for match in result.matches] == ["https://catfk.com/item/KEY1", "https://catfk.com/item/KEY2"]
    assert result.matches[0].listed_price == 29.9
    assert result.matches[0].stock_count == 3
    assert intake_result_payload(result) == ("validated", 2, "")


def test_same_upstream_token_and_goods_keys_keep_separate_candidates_and_matches(tmp_path):
    db = StateDB(tmp_path / "crawler.db")
    try:
        discovery = Discovery(db, MagicMock(), timeout=5, max_discovered=10, logger=logging.getLogger("catfk-discovery"))
        assert discovery.from_seeds([OFFICIAL_URL, CATFK_URL], None) == 2
        for intake_id, source_url in enumerate((OFFICIAL_URL, CATFK_URL), start=1):
            db.upsert_intake_candidate(
                intake_id=intake_id,
                token=intake_claim_token(source_url),
                url=source_url,
                shop_name="Fixture shop",
                attempt_count=2,
            )
            result, _, _ = scan_fixture(scanner_for(tmp_path), source_url)
            db.save_scan_result(result, None)
        candidates = {row["token"]: dict(row) for row in db.conn.execute("SELECT * FROM candidates")}
        assert set(candidates) == {"I8WO6J9O", "catfk:I8WO6J9O"}
        assert candidates["I8WO6J9O"]["intake_id"] == 1
        assert candidates["catfk:I8WO6J9O"]["intake_id"] == 2
        assert candidates["catfk:I8WO6J9O"]["url"] == CATFK_URL
        rows = list(db.conn.execute("SELECT token, product_key, product_url FROM matches ORDER BY token, product_key"))
        assert len(rows) == 4
        assert len({(row["token"], row["product_key"]) for row in rows}) == 4
        assert all(row["product_url"].startswith("https://catfk.com/") for row in rows if row["token"].startswith("catfk:"))
    finally:
        db.close()


def test_catfk_api_drops_off_origin_request_template(tmp_path):
    scanner = scanner_for(tmp_path)
    page = MagicMock()
    page.url = CATFK_URL
    page.evaluate.return_value = {"status": 200, "text": '{"code": 1, "data": {}}'}
    capture = CaptureState(templates={INFO_ENDPOINT: RequestTemplate(
        "https://pay.ldxp.cn" + INFO_ENDPOINT,
        {"token": "OTHER", "foreign_field": True},
        {"authorization": "foreign-value"},
    )})
    scanner._fetch_api(page, capture, INFO_ENDPOINT, {"token": "I8WO6J9O"})
    args = page.evaluate.call_args.args[1]
    assert args["url"] == "https://catfk.com" + INFO_ENDPOINT
    assert args["payload"] == {"token": "I8WO6J9O"}
    assert args["headers"] == {}


def test_catfk_scan_rejects_redirect_to_different_merchant_namespace(tmp_path):
    scanner = scanner_for(tmp_path)
    page = MagicMock()
    page.url = OFFICIAL_URL
    page.goto.return_value.status = 200
    scanner._new_page_with_capture = lambda: (page, CaptureState())
    scanner._is_challenge = lambda _page: False
    result = scanner.scan_shop({"token": "catfk:I8WO6J9O", "url": CATFK_URL}, ["gpt"])
    assert result.status == "api_changed"
    assert result.shop_url == CATFK_URL
    page.evaluate.assert_not_called()
