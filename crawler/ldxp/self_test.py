from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from ldxp_crawler.browser_scanner import BrowserShopScanner, has_target_brand
from ldxp_crawler.db import StateDB
from ldxp_crawler.exporter import export_results
from ldxp_crawler.models import ProductMatch, ShopScanResult
from ldxp_crawler.utils import CHALLENGE_RE, extract_shop_urls


def create_v1_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE candidates (
            token TEXT PRIMARY KEY, url TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]',
            discovered_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', shop_name TEXT, shop_url TEXT,
            api_host TEXT, scanned_item_count INTEGER NOT NULL DEFAULT 0,
            hit_count INTEGER NOT NULL DEFAULT 0, scanned_at TEXT, last_error TEXT
        );
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL, shop_name TEXT,
            shop_url TEXT, api_host TEXT, product_key TEXT, product_name TEXT NOT NULL,
            matched_keywords TEXT NOT NULL, listed_price REAL, real_price REAL,
            stock_count INTEGER, product_status TEXT, category_name TEXT, product_url TEXT,
            auto_delivery TEXT, goods_type TEXT, raw_json TEXT, collected_at TEXT NOT NULL,
            UNIQUE(token, product_key, product_name)
        );
        INSERT INTO candidates(token,url,sources,discovered_at,updated_at,status)
        VALUES ('TEST01','https://pay.ldxp.cn/shop/TEST01','["seed"]','2026-01-01','2026-01-01','pending');
        """
    )
    conn.commit()
    conn.close()


def main() -> None:
    assert extract_shop_urls("pay.ldxp.cn/shop/ABC123") == ["https://pay.ldxp.cn/shop/ABC123"]
    assert CHALLENGE_RE.search("<html><script>var arg1='ABC123';</script></html>")
    assert BrowserShopScanner._extract_items({"data": {"list": [{"id": 1}]}}) == [{"id": 1}]
    assert BrowserShopScanner._extract_total({"data": {"total": 12}}) == 12
    assert has_target_brand("SuperGrok 代充值")
    assert has_target_brand("X（Twitter） Premium会员直充卡密")
    assert not has_target_brand("Twitter 普通账号")
    assert has_target_brand("plus成品号", "chat plus 成品号")
    assert has_target_brand("谷歌邮件 成品 Plus", "全部")
    assert not has_target_brand("Google Gmail 老号", "谷歌账号")
    assert not has_target_brand("百度网盘 Plus 成品号", "网盘账号")
    assert not has_target_brand("gm ic邮箱 Free 已开通2fa，百分百0元优惠，开plus专用", "GPT Free")
    assert not has_target_brand("谷歌邮箱成品老号，带2FA", "Gemini")
    assert has_target_brand("高级会员直充一个月", "Claude")
    scanner = object.__new__(BrowserShopScanner)
    matches = scanner._build_matches(
        [
            {"id": "1", "name": "Google Gmail 老号", "description": "支持 ChatGPT"},
            {"id": "2", "name": "StyleMe Chrome插件 API额度", "category_name": "浏览器插件"},
            {"id": "3", "name": "ChatGPT Plus 直充一个月"},
            {"id": "4", "name": "SuperGrok 代充值"},
            {"id": "5", "name": "X Premium+ 12个月官方直充"},
        ],
        ["gpt", "chatgpt", "openai", "grok", "supergrok", "x premium"],
        "https://pay.ldxp.cn/shop/TEST01",
        False,
    )
    assert [item.product_name for item in matches] == ["ChatGPT Plus 直充一个月", "SuperGrok 代充值", "X Premium+ 12个月官方直充"]
    replay_headers = BrowserShopScanner._safe_replay_headers(
        {"User-Agent": "bad", "visitorid": "stable", "X-App": "ok", "Cookie": "secret"}
    )
    assert replay_headers == {"visitorid": "stable", "X-App": "ok"}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "v1.db"
        create_v1_database(db_path)
        db = StateDB(db_path)
        assert "source_score" in {row[1] for row in db.conn.execute("PRAGMA table_info(candidates)")}
        run_id = db.start_run("self_test", ["gpt"], "browser", {})
        success = ShopScanResult(
            token="TEST01",
            status="success",
            shop_name="=不可信店名",
            shop_url="https://pay.ldxp.cn/shop/TEST01",
            api_host="pay.ldxp.cn",
            scanned_item_count=1,
            matches=[
                ProductMatch(
                    product_key="P1",
                    product_name="=HYPERLINK(\"https://example.invalid\",\"x\")",
                    matched_keywords=["gpt"],
                    listed_price=19.9,
                    product_status="有货",
                    product_url="javascript:alert(1)",
                    raw={"name": "test"},
                )
            ],
        )
        db.save_scan_result(success, run_id)
        count_before = db.conn.execute("SELECT COUNT(*) FROM matches WHERE token='TEST01'").fetchone()[0]
        assert count_before == 1
        assert [row["token"] for row in db.list_candidates(rescan=True, matched_only=True)] == ["TEST01"]

        # A transient failure must not erase previous successful matches.
        db.save_scan_result(
            ShopScanResult(token="TEST01", status="network_error", error="temporary"),
            run_id,
        )
        count_after = db.conn.execute("SELECT COUNT(*) FROM matches WHERE token='TEST01'").fetchone()[0]
        assert count_after == 1

        db.save_scan_result(
            ShopScanResult(token="TEST01", status="challenge_required", error="verification required"),
            run_id,
        )
        assert db.list_candidates(rescan=True) == []
        assert [row["token"] for row in db.list_candidates(rescan=True, retry_blocked=True)] == ["TEST01"]

        db.finish_run(
            run_id,
            attempted=2,
            successful=1,
            failed=1,
            blocked=0,
            matches=1,
            circuit_broken=False,
        )
        paths = export_results(db, root / "output", "selftest")
        db.close()

        wb = load_workbook(paths["xlsx"], data_only=False)
        assert wb["匹配商品"]["D2"].value.startswith("'")
        assert wb["匹配商品"]["K2"].hyperlink is None
        assert wb["运行摘要"]["A1"].value == "指标"
        print("SELF TEST PASSED")
        print(paths["xlsx"])


if __name__ == "__main__":
    main()
