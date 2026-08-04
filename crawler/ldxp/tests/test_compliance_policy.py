from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from ldxp_crawler.db import StateDB
from ldxp_crawler.header_policy import assert_no_blocked_headers, is_blocked_header, sanitize_headers
from ldxp_crawler.models import ProductMatch, ShopScanResult
from ldxp_crawler.policy import CollectionDecision, CollectionPolicyGate, candidate_origin
from ldxp_crawler.public_dom_scanner import (
    build_product_match,
    content_hash,
    is_challenge_text,
    is_login_wall,
    parse_public_price,
    parse_public_stock,
)
from ldxp_crawler.scheduler import DueShopScheduler
from ldxp_crawler.sensitive_data import redact_text, sensitive_hits
from ldxp_crawler.utils import utc_now


def test_header_policy_blocks_sensitive_headers():
    for name in ("Authorization", "cookie", "visitorid", "X-Api-Key", "app-token", "device-id", "sec-fetch-site", "x-custom"):
        assert is_blocked_header(name)
    assert not is_blocked_header("Accept-Language")
    sanitized = sanitize_headers({"Authorization": "Bearer x", "Cookie": "a=b", "Accept-Language": "zh-CN"})
    assert sanitized == {"Accept-Language": "zh-CN"}
    with pytest.raises(ValueError):
        assert_no_blocked_headers({"visitorid": "x"})


def test_sensitive_data_detects_and_redacts():
    text = "联系 13800138000 或 abc@example.com 微信 wxid_abcdefgh"
    hits = sensitive_hits(text)
    assert "phone" in hits and "email" in hits and "wechat" in hits
    redacted, _ = redact_text(text)
    assert "13800138000" not in redacted and "abc@example.com" not in redacted
    assert "[redacted]" in redacted
    assert sensitive_hits("普通商品名称") == []


def test_public_dom_parsing_and_minimal_match():
    assert parse_public_price("¥88.00") == 88.0
    assert parse_public_price("无价格") is None
    assert parse_public_stock("现货 有货") == "in_stock"
    assert parse_public_stock("缺货") == "out_of_stock"
    assert parse_public_stock("已下架") == "unavailable"
    match = build_product_match(
        product_key="P1",
        name="ChatGPT Plus 直充一个月",
        price=88.0,
        stock="in_stock",
        product_url="https://pay.ldxp.cn/shop/TEST01/item/P1",
        shop_closed=False,
        keywords=["gpt", "chatgpt"],
    )
    assert match is not None
    assert match.listed_price == 88.0
    assert match.product_status == "有货"
    assert match.content_hash
    assert match.redacted_field_count == 0
    assert build_product_match(
        product_key="P2",
        name="ChatGPT 微信: wxid_abcdefgh",
        price=1.0,
        stock="in_stock",
        product_url="https://pay.ldxp.cn/shop/TEST01/item/P2",
        shop_closed=False,
        keywords=["chatgpt"],
    ) is None
    assert is_challenge_text("人机验证，请完成安全验证")
    assert is_login_wall("请登录后查看商品详情")
    assert not is_login_wall("首页有登录导航按钮")
    assert parse_public_price("GPT-4 30天套餐 ¥88.00") == 88.0
    assert parse_public_price("GPT-4 30天套餐") is None
    assert parse_public_price("GPT-4 30天套餐", price_element_text="¥99.00") == 99.0
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_public_dom_scanner_source_has_no_forbidden_capabilities():
    root = Path(__file__).resolve().parents[1]
    source = (root / "ldxp_crawler" / "public_dom_scanner.py").read_text(encoding="utf-8")
    for forbidden in (
        "launch_persistent_context",
        "user_data_dir",
        "add_cookies",
        "localStorage.setItem",
        "add_init_script",
        "/shopApi/",
        "visitorid",
    ):
        assert forbidden not in source
    wrapper = (root / "ldxp_crawler" / "browser_scanner.py").read_text(encoding="utf-8")
    for forbidden in (
        "launch_persistent_context",
        "user_data_dir",
        "add_cookies",
        "localStorage",
        "/shopApi/",
        "_safe_replay_headers",
        "_fetch_api",
    ):
        assert forbidden not in wrapper


def _active_candidate(token: str = "TEST01", **overrides) -> dict:
    row = {
        "token": token,
        "url": f"https://pay.ldxp.cn/shop/{token}",
        "policy_status": "active",
        "policy_reason": "",
        "blocked_until": "",
        "next_scan_at": "2000-01-01T00:00:00+00:00",
        "daily_request_date": "",
        "daily_request_count": 0,
    }
    row.update(overrides)
    return row


def test_policy_gate_order_and_sticky_statuses():
    gate = CollectionPolicyGate(enabled=False, mode="public_dom", environ={})
    decision = gate.decide(_active_candidate())
    assert not decision.allowed and "disabled by policy" in decision.reason

    gate = CollectionPolicyGate(enabled=True, mode="public_dom", environ={})
    for status in ("opted_out", "legal_hold", "unsupported"):
        decision = gate.decide(_active_candidate(policy_status=status))
        assert not decision.allowed
        assert status in decision.reason

    decision = gate.decide(_active_candidate(blocked_until="2999-01-01T00:00:00+00:00"))
    assert not decision.allowed and "blocked" in decision.reason

    decision = gate.decide(_active_candidate(next_scan_at="2999-01-01T00:00:00+00:00"))
    assert not decision.allowed and "not due" in decision.reason

    decision = gate.decide(_active_candidate(daily_request_date=utc_now()[:10], daily_request_count=12))
    assert not decision.allowed and "daily budget" in decision.reason

    decision = gate.decide(_active_candidate(policy_reason="robots-denied"))
    assert not decision.allowed and "robots" in decision.reason

    decision = gate.decide(_active_candidate())
    assert decision.allowed and decision.mode == "public_dom"


def test_policy_gate_fails_closed_on_origin_checker_error():
    def broken(_origin: str) -> CollectionDecision:
        raise RuntimeError("api down")

    gate = CollectionPolicyGate(enabled=True, mode="public_dom", source_checker=broken, environ={})
    decision = gate.decide(_active_candidate())
    assert not decision.allowed and "unavailable" in decision.reason


def test_policy_gate_passes_full_shop_url_to_source_checker():
    received: list[str] = []

    def checker(source_url: str) -> CollectionDecision:
        received.append(source_url)
        return CollectionDecision(True, "public_dom", "allowed")

    gate = CollectionPolicyGate(enabled=True, mode="public_dom", source_checker=checker, environ={})
    decision = gate.decide(_active_candidate("TEST01", url="https://pay.ldxp.cn/shop/TEST01"))
    assert decision.allowed
    assert received == ["https://pay.ldxp.cn/shop/TEST01"]


def test_robots_txt_policy_respects_disallow():
    from ldxp_crawler.policy import RobotsTxtPolicy

    def fetcher(url: str) -> tuple[int, str]:
        return 200, "User-agent: *\nDisallow: /shop/TEST01\n"

    policy = RobotsTxtPolicy(fetcher=fetcher)
    allowed, reason = policy.allows("https://pay.ldxp.cn/shop/TEST01")
    assert not allowed
    assert reason.startswith("robots-denied")
    allowed, _reason = policy.allows("https://pay.ldxp.cn/shop/TEST02")
    assert allowed


def test_unchanged_hash_slows_interval_and_change_resets(tmp_path: Path):
    db = StateDB(tmp_path / "hash.db")
    try:
        db.upsert_candidate("HASH", "https://pay.ldxp.cn/shop/HASH", "seed", 100)
        match = ProductMatch(
            product_key="P1",
            product_name="ChatGPT Plus",
            matched_keywords=["chatgpt"],
            listed_price=99.0,
            product_status="有货",
            product_url="https://pay.ldxp.cn/shop/HASH/item/P1",
            content_hash="same-hash",
        )
        run_id = db.start_run("scan", ["chatgpt"], "public_dom", {})
        db.save_scan_result(
            ShopScanResult(token="HASH", status="success", scanned_item_count=1, matches=[match]),
            run_id,
        )
        row = db.conn.execute("SELECT * FROM candidates WHERE token='HASH'").fetchone()
        assert row["scan_interval_minutes"] == 60

        db.save_scan_result(
            ShopScanResult(token="HASH", status="success", scanned_item_count=1, matches=[match]),
            run_id,
        )
        row = db.conn.execute("SELECT * FROM candidates WHERE token='HASH'").fetchone()
        assert row["scan_interval_minutes"] == 120
        assert row["unchanged_streak"] == 1

        changed = ProductMatch(
            product_key="P1",
            product_name="ChatGPT Plus",
            matched_keywords=["chatgpt"],
            listed_price=88.0,
            product_status="有货",
            product_url="https://pay.ldxp.cn/shop/HASH/item/P1",
            content_hash="different-hash",
        )
        db.save_scan_result(
            ShopScanResult(token="HASH", status="success", scanned_item_count=1, matches=[changed]),
            run_id,
        )
        row = db.conn.execute("SELECT * FROM candidates WHERE token='HASH'").fetchone()
        assert row["scan_interval_minutes"] == 60
        assert row["unchanged_streak"] == 0
    finally:
        db.close()


def test_backoff_wakes_up_after_blocked_until_expires(tmp_path: Path):
    db = StateDB(tmp_path / "wake.db")
    try:
        db.upsert_candidate("WAKE", "https://pay.ldxp.cn/shop/WAKE", "seed", 100)
        db.conn.execute(
            "UPDATE candidates SET policy_status='blocked', blocked_until=?, next_scan_at=?, scan_interval_minutes=10080 WHERE token='WAKE'",
            ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"),
        )
        db.conn.commit()
        due = db.list_due_candidates(limit=10)
        assert [row["token"] for row in due] == ["WAKE"]
        gate = CollectionPolicyGate(enabled=True, mode="public_dom", environ={})
        decision = gate.decide(due[0])
        assert decision.allowed

        scans = []

        class FakeScanner:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def scan_shop(self, candidate, keywords):
                scans.append(candidate["token"])
                return ShopScanResult(
                    token=candidate["token"],
                    status="no_match",
                    request_count=1,
                )

        scheduler = DueShopScheduler(
            db,
            gate,
            scanner_factory=FakeScanner,
            logger=logging.getLogger("test-wake"),
            batch_limit=10,
        )
        summary = scheduler.run_once([])
        assert summary["scanned"] == 1
        assert scans == ["WAKE"]
        row = db.conn.execute("SELECT * FROM candidates WHERE token='WAKE'").fetchone()
        assert row["policy_status"] == "active"
        assert row["blocked_until"] is None
    finally:
        db.close()


def test_global_request_budget_uses_real_request_counts(tmp_path: Path):
    db = StateDB(tmp_path / "budget.db")
    try:
        db.upsert_candidate("BUDGET", "https://pay.ldxp.cn/shop/BUDGET", "seed", 100)
        db.conn.execute(
            "UPDATE candidates SET daily_request_count=1, daily_request_date=? WHERE token='BUDGET'",
            (utc_now()[:10],),
        )
        db.conn.commit()

        class HeavyScanner:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def scan_shop(self, candidate, keywords):
                return ShopScanResult(
                    token=candidate["token"],
                    status="no_match",
                    request_count=5,
                )

        gate = CollectionPolicyGate(
            enabled=True,
            mode="public_dom",
            daily_global_budget=1,
            environ={},
        )
        scheduler = DueShopScheduler(
            db,
            gate,
            scanner_factory=HeavyScanner,
            logger=logging.getLogger("test-budget"),
            batch_limit=10,
        )
        summary = scheduler.run_once([])
        assert summary["scanned"] == 0
        assert summary["attempted"] == 0

        budget_limited = CollectionPolicyGate(
            enabled=True,
            mode="public_dom",
            daily_global_budget=4,
            environ={},
        )
        scheduler = DueShopScheduler(
            db,
            budget_limited,
            scanner_factory=HeavyScanner,
            logger=logging.getLogger("test-budget-2"),
            batch_limit=10,
        )
        summary = scheduler.run_once([])
        assert summary["scanned"] == 1  # first shop starts within budget, then stops
    finally:
        db.close()


def test_due_scheduler_claims_once_and_respects_daily_budget(tmp_path: Path):
    db = StateDB(tmp_path / "scheduler.db")
    try:
        db.upsert_candidate("TEST01", "https://pay.ldxp.cn/shop/TEST01", "seed", 100)
        db.upsert_candidate("TEST02", "https://pay.ldxp.cn/shop/TEST02", "seed", 90)
        due = db.list_due_candidates(limit=10)
        assert {row["token"] for row in due} == {"TEST01", "TEST02"}

        class FakeScanner:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def scan_shop(self, candidate, keywords):
                return ShopScanResult(
                    token=candidate["token"],
                    status="success",
                    shop_name="Test",
                    shop_url=candidate["url"],
                    scanned_item_count=1,
                    matches=[
                        ProductMatch(
                            product_key="P1",
                            product_name="ChatGPT Plus",
                            matched_keywords=["chatgpt"],
                            listed_price=99.0,
                            product_status="有货",
                            product_url=candidate["url"] + "/item/P1",
                            content_hash="hash-1",
                        )
                    ],
                )

        gate = CollectionPolicyGate(enabled=True, mode="public_dom", max_scans_per_shop_day=1, environ={})
        scheduler = DueShopScheduler(
            db,
            gate,
            scanner_factory=FakeScanner,
            logger=logging.getLogger("test-scheduler"),
            batch_limit=10,
        )
        summary = scheduler.run_once(["chatgpt"])
        assert summary["scanned"] == 2
        assert summary["matches"] == 2
        rows = {row["token"]: row for row in db.conn.execute("SELECT * FROM candidates").fetchall()}
        assert rows["TEST01"]["policy_status"] == "active"
        assert rows["TEST01"]["scan_interval_minutes"] == 60
        assert rows["TEST01"]["daily_request_count"] == 1

        # Daily budget exhausted on second run.
        summary = scheduler.run_once(["chatgpt"])
        assert summary["attempted"] == 0
        assert summary["deferred"] == 0
    finally:
        db.close()


def test_scheduler_sets_long_backoff_for_blocked_and_challenge(tmp_path: Path):
    db = StateDB(tmp_path / "backoff.db")
    try:
        db.upsert_candidate("BLOCK", "https://pay.ldxp.cn/shop/BLOCK", "seed", 100)

        class BlockScanner:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def scan_shop(self, candidate, keywords):
                return ShopScanResult(token=candidate["token"], status="blocked", http_status=403)

        gate = CollectionPolicyGate(enabled=True, mode="public_dom", environ={})
        scheduler = DueShopScheduler(
            db,
            gate,
            scanner_factory=BlockScanner,
            logger=logging.getLogger("test-backoff"),
            batch_limit=10,
        )
        scheduler.run_once([])
        row = db.conn.execute("SELECT * FROM candidates WHERE token='BLOCK'").fetchone()
        assert row["status"] == "blocked"
        assert row["policy_status"] == "blocked"
        assert row["scan_interval_minutes"] == 10080
        assert row["blocked_until"] == row["next_scan_at"]
        assert db.list_due_candidates(limit=10) == []
    finally:
        db.close()


def test_candidate_origin_normalization():
    assert candidate_origin("https://pay.ldxp.cn/shop/TEST01") == "https://pay.ldxp.cn"
    assert candidate_origin("http://shop.example.com/x") == "https://shop.example.com"
