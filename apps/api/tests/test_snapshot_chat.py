from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.catalog_vocabulary import account_access
from app.services import bot_ai_settings
from app.services.snapshot_catalog import SnapshotStore
from extensions.bots import chat_commands, snapshot_chat


@pytest.fixture
def chat(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_ai_settings, "load_runtime_config", lambda: bot_ai_settings.BotAIConfig())
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path))
    store = SnapshotStore()
    monkeypatch.setattr(snapshot_chat, "snapshot_store", store)
    bot = snapshot_chat.SnapshotChat()
    monkeypatch.setattr(snapshot_chat, "snapshot_chat", bot)

    def no_database(*args, **kwargs):
        raise AssertionError("Quote search must not open a database connection")
    monkeypatch.setattr(chat_commands, "SessionLocal", no_database)
    now = datetime.now(timezone.utc).isoformat()
    offers = [{
        "id": index + 1, "shop_name": f"商家{index + 1}", "shop_token": f"shop-{index + 1}",
        "original_name": f"Claude Pro {'独享' if index >= 5 else '成品号'}", "price": 50 + index * 10,
        "currency": "CNY", "stock_status": "in_stock", "stock_count": 2,
        "delivery_type": "finished_account", "service_period": "one_month" if index % 2 else "one_year",
        "account_access": "exclusive" if index >= 5 else "unknown", "warranty": "subscription_term",
        "is_comparable": True, "is_trusted_price": True, "observed_at": now,
        "source_url": f"https://example.com/{index + 1}", "item_fingerprint": f"item-{index + 1}",
    } for index in range(9)]
    product = {
        "slug": "claude-pro", "brand": "Claude", "display_name": "Claude Pro", "brand_aliases": ["claude", "克劳德"],
        "search_aliases": ["claude-pro", "Claude Pro", "pro"], "offers": offers,
        "offer_count": len(offers), "comparable_offer_count": len(offers),
    }
    data = {"search_schema_version": 1, "stale_offer_hours": 72, "snapshot_id": "1", "published_at": now, "products": [product], "offer_count": len(offers)}
    def publish(snapshot_id="1"):
        data["snapshot_id"] = snapshot_id
        directory = tmp_path / "v1" / "snapshots"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{snapshot_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (tmp_path / "latest.json").write_text(json.dumps({"snapshot_id": snapshot_id}), encoding="utf-8")
    publish()
    return bot, data, publish, store


def test_search_full_snapshot_with_combined_filters_and_followups(chat):
    bot, _, _, _ = chat
    reply = chat_commands.handle_chat_command("帮我找 Claude Pro，独享，月付，110元以内", sender_id="alice")
    assert "商家6" in reply and "¥100.00" in reply
    assert "商家1" not in reply and "商家8" not in reply
    detail = bot.reply("第一家", sender_id="alice")
    assert "https://example.com/6" in detail
    assert "未找到" in bot.reply("90元以内", sender_id="alice")
    reset = bot.reply("清除筛选", sender_id="alice")
    assert "商家1" in reset


def test_pagination_isolation_and_anonymous_requests(chat):
    bot, _, _, _ = chat
    bot.reply("claude pro", sender_id="alice", account_id="a", conversation_id="group:1")
    page = bot.reply("下一页", sender_id="alice", account_id="a", conversation_id="group:1")
    assert "商家6" in page and "商家1（" not in page
    detail = bot.reply("第二家", sender_id="alice", account_id="a", conversation_id="group:1")
    assert "https://example.com/7" in detail
    for context in (
        dict(sender_id="bob", account_id="a", conversation_id="group:1"),
        dict(sender_id="alice", account_id="b", conversation_id="group:1"),
        dict(sender_id="alice", account_id="a", conversation_id="group:2"),
        dict(sender_id="alice", account_id="a", conversation_id="c2c"),
        dict(sender_id="alice", channel="telegram", account_id="a", conversation_id="group:1"),
    ):
        assert "请先搜索" in bot.reply("下一页", **context)
    bot.reply("claude pro")
    assert "请先搜索" in bot.reply("第二家")


def test_snapshot_switch_refreshes_numbered_results_and_reuses_cache(chat):
    bot, data, publish, store = chat
    first = store.load()
    assert store.load() is first
    bot.reply("claude pro", sender_id="alice")
    data["products"][0]["offers"][0]["price"] = 999
    publish("2")
    reply = bot.reply("第一家", sender_id="alice")
    assert "报价已更新" in reply
    assert "https://example.com/1" not in reply
    assert store.load() is not first
    assert "https://example.com/2" in bot.reply("第一家", sender_id="alice")


def test_unknown_access_is_not_exclusive_and_currency_is_not_mixed(chat):
    bot, data, publish, _ = chat
    data["products"][0]["offers"][5].update(currency="USD", is_trusted_price=False)
    publish("2")
    reply = bot.reply("claude pro 不要共享 月付 150元以内", sender_id="alice")
    assert "商家8" in reply and "商家6" not in reply and "商家2" not in reply
    reply = bot.reply("claude pro 120美元以内", sender_id="alice")
    assert "USD 100.00" in reply and "商家1（" not in reply


def test_missing_legacy_incomplete_and_stale_snapshots_fail_closed(chat, tmp_path):
    bot, data, publish, _ = chat
    data.pop("search_schema_version")
    publish("2")
    assert "需要更新" in bot.reply("claude pro")
    data["search_schema_version"] = 1
    data["products"][0]["offers"].pop()
    publish("3")
    assert "不完整" in bot.reply("claude pro")
    data["products"][0]["offer_count"] -= 1
    data["products"][0]["comparable_offer_count"] -= 1
    data["offer_count"] -= 1
    data["published_at"] = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    publish("4")
    assert "过期" in bot.reply("claude pro")
    (tmp_path / "latest.json").write_text('{"snapshot_id":"../private"}', encoding="utf-8")
    assert "标识无效" in bot.reply("claude pro")


def test_filters_preserve_constraints_and_invalid_budget_does_not_change_session(chat):
    bot, _, _, _ = chat
    bot.reply("claude pro", sender_id="alice")
    bot.reply("只看月付", sender_id="alice")
    reply = bot.reply("80到110元", sender_id="alice")
    assert "商家4" in reply and "商家6" in reply and "商家5" not in reply
    assert "下限高于上限" in bot.reply("200元以上", sender_id="alice")
    assert "https://example.com/4" in bot.reply("第一家", sender_id="alice")


def test_switching_shared_to_exclusive_restores_trusted_scope(chat):
    bot, data, publish, _ = chat
    offers = data["products"][0]["offers"]
    offers[0].update(account_access="shared", is_comparable=False, is_trusted_price=False)
    offers[5].update(is_trusted_price=False)
    publish("2")
    assert "商家1（" in bot.reply("claude pro 共享", sender_id="alice")
    reply = bot.reply("只看独享", sender_id="alice")
    assert "商家7" in reply and "商家6" not in reply and "商家1（" not in reply


def test_free_text_terms_and_shop_filters_keep_the_selected_product(chat):
    bot, data, publish, _ = chat
    data["products"][0]["offers"][5]["original_name"] += " 美区 原生账号"
    publish("2")
    reply = bot.reply("Claude Pro 美区 原生", sender_id="alice")
    assert "商家6" in reply and "商家7" not in reply
    reply = bot.reply("只看商家6", sender_id="alice")
    assert "Claude Pro" in reply and "商家6" in reply
    assert "https://example.com/6" in bot.reply("第一家", sender_id="alice")


@pytest.mark.parametrize("command", ["不要年付", "不独享", "非独享", "排除成品号"])
def test_unsupported_negations_do_not_change_the_previous_selection(chat, command):
    bot, _, _, _ = chat
    bot.reply("claude pro", sender_id="alice")
    assert "暂不支持这个排除条件" in bot.reply(command, sender_id="alice")
    assert "https://example.com/1" in bot.reply("第一家", sender_id="alice")


def test_warranty_duration_is_not_mistaken_for_subscription_period(chat):
    bot, data, publish, _ = chat
    data["products"][0]["offers"][5]["warranty"] = "seven_days"
    publish("2")
    reply = bot.reply("Claude Pro 月付 7天质保", sender_id="alice")
    assert "商家6" in reply and "商家2" not in reply


def test_price_constraints_do_not_become_product_tier_names(chat):
    _, _, _, store = chat
    catalog = store.load()
    query = snapshot_chat.parse_query("ChatGPT Pro 100元以内", catalog)
    assert query.product == "chatgpt-pro" and query.max_price == Decimal("100")
    query = snapshot_chat.parse_query("ChatGPT Pro 100 150元以内", catalog)
    assert query.product == "chatgpt-pro-100" and query.max_price == Decimal("150")
    query = snapshot_chat.parse_query("Claude Pro 预算 80 到 110 元", catalog)
    assert query.product == "claude-pro" and query.min_price == Decimal("80") and query.max_price == Decimal("110")


def test_numbered_details_preserve_trusted_representative_and_clear_after_overview(chat):
    bot, data, publish, _ = chat
    offers = data["products"][0]["offers"]
    offers[0].update(item_fingerprint="same-item", is_trusted_price=False)
    offers[5].update(item_fingerprint="same-item")
    publish("2")
    bot.reply("claude pro 独享", sender_id="alice")
    assert "https://example.com/6" in bot.reply("第一家", sender_id="alice")
    assert "全系列" in bot.reply("查询 claude", sender_id="alice")
    assert "没有这个序号" in bot.reply("第一家", sender_id="alice")
    bot.reply("行情", sender_id="alice")
    assert "请先搜索" in bot.reply("第一家", sender_id="alice")


def test_sessions_expire_and_remain_bounded(chat, monkeypatch):
    bot, _, _, _ = chat
    monkeypatch.setattr(snapshot_chat.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(snapshot_chat, "MAX_SESSIONS", 2)
    for sender in ("alice", "bob", "charlie"):
        bot.reply("claude pro", sender_id=sender)
    assert len(bot.sessions) == 2
    assert "请先搜索" in bot.reply("下一页", sender_id="alice")
    monkeypatch.setattr(snapshot_chat.time, "monotonic", lambda: 100.0 + snapshot_chat.SESSION_TTL)
    assert "请先搜索" in bot.reply("下一页", sender_id="bob")
    assert not bot.sessions


@pytest.mark.parametrize(("field", "value"), [("price", "broken"), ("price", "NaN"), ("warranty", None), ("is_trusted_price", "true"), ("observed_at", "not-a-date"), ("id", 2)])
def test_malformed_quote_never_installs_a_partial_snapshot(chat, field, value):
    bot, data, publish, store = chat
    initial = store.load()
    data["products"][0]["offers"][0][field] = value
    publish("2")
    reply = bot.reply("claude pro")
    assert "快照" in reply and "商家" not in reply
    assert store._catalog is initial


def test_missing_or_corrupt_pointer_does_not_fall_back_to_cached_prices(chat, tmp_path):
    bot, _, _, store = chat
    store.load()
    pointer = tmp_path / "latest.json"
    pointer.write_text("broken-json", encoding="utf-8")
    assert "暂时无法读取" in bot.reply("claude pro")
    pointer.unlink()
    assert "暂时无法读取" in bot.reply("claude pro")


def test_quote_freshness_uses_the_published_policy(chat):
    bot, data, publish, _ = chat
    data["stale_offer_hours"] = 24
    data["products"][0]["offers"][0]["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    publish("2")
    reply = bot.reply("claude pro", sender_id="alice")
    assert "商家1（" not in reply and "商家2" in reply
    data["published_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    publish("3")
    assert "过期" in bot.reply("claude pro")


@pytest.mark.parametrize(("title", "delivery", "expected"), [
    ("Plus 独享", "finished_account", "exclusive"),
    ("Plus 成品号", "finished_account", "unknown"),
    ("Plus 不独享", "finished_account", "unknown"),
    ("Plus 非共享", "finished_account", "exclusive"),
    ("Plus 独享", "shared_pool", "shared"),
])
def test_access_classification_is_conservative(title, delivery, expected):
    assert account_access(title, delivery) == expected
