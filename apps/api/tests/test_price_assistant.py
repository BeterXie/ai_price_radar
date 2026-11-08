from __future__ import annotations

import asyncio
import json
import threading

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from test_snapshot_chat import chat  # Shared realistic snapshot fixture, including the no-DB guard.
from app.schemas import BotAISettingsUpdate
from app.services import bot_ai_settings
from extensions.bots import chat_commands, price_assistant, snapshot_chat


@pytest.fixture
def provider(monkeypatch):
    config = bot_ai_settings.BotAIConfig(
        enabled=True, base_url="https://model.example/v1", model="test-tool-model",
        api_key=SecretStr("not-a-real-key"), api_style="chat_completions",
    )
    monkeypatch.setattr(bot_ai_settings, "load_runtime_config", lambda: config)
    monkeypatch.setattr(snapshot_chat, "price_assistant", price_assistant.PriceAssistant())
    state = {"plan": {}, "calls": [], "config": config}
    real_client = httpx.Client

    def handle(request):
        payload = json.loads(request.content)
        state["calls"].append(payload)
        assert request.headers["authorization"] == "Bearer not-a-real-key"
        assert payload["model"] == "test-tool-model"
        assert payload["store"] is False
        if "callback" in state:
            state["callback"]()
        if state.get("timeout"):
            raise httpx.ReadTimeout("private provider response must not be logged")
        if "body" in state:
            return httpx.Response(state.get("status", 200), json=state["body"])
        function = {"name": state.get("tool", "plan_price_request"), "arguments": json.dumps(state["plan"], ensure_ascii=False)}
        if config.api_style == "responses":
            assert request.url.path == "/v1/responses"
            return httpx.Response(200, json={"output": [{"type": "function_call", **function}]})
        assert request.url.path == "/v1/chat/completions"
        # Free text must never become a quote or recommendation.
        return httpx.Response(200, json={"choices": [{"message": {"content": "编造店铺一分钱保证永不封号", "tool_calls": [{"type": "function", "function": function}]}}]})

    monkeypatch.setattr(price_assistant.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    return state


def ask(text, **kwargs):
    return chat_commands.handle_chat_command(text, sender_id="private-user", account_id="private-app", conversation_id="group:private-group", **kwargs)


def test_ai_interprets_filters_and_keeps_all_prices_in_the_snapshot(chat, provider):
    _, data, publish, _ = chat
    offers = data["products"][0]["offers"]
    offers[1]["delivery_type"] = "semi_finished_account"
    offers[3]["delivery_type"] = "subscription_recharge"
    publish("2")
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro", "delivery": "account", "period": "one_month", "max_price": 110}]}
    reply = ask("想要克劳德会员账号，每月一百一以内，没做完的号也行")
    assert "商家2" in reply and "商家6" in reply and "商家4" not in reply
    assert "¥60.00" in reply and "¥100.00" in reply
    assert "编造店铺" not in reply and "账号（成品 / 半成品）" in reply
    payload = json.dumps(provider["calls"][0], ensure_ascii=False)
    for secret in ("private-user", "private-app", "private-group", "not-a-real-key"):
        assert secret not in payload


def test_ai_followup_preserves_budget_and_explains_without_losing_results(chat, provider):
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro", "max_price": 110}]}
    ask("找个一百一以内的Claude会员")
    provider["plan"] = {"action": "search", "searches": [{"inherit": True, "period": "one_month"}]}
    reply = ask("那就每月付一次的吧")
    assert "商家2" in reply and "商家7" not in reply
    context = json.loads(provider["calls"][-1]["messages"][1]["content"])
    assert context["previous_query"]["max_price"] == "110"
    provider["plan"] = {"action": "explain", "topics": ["account", "semi_finished", "recharge", "period_warranty"]}
    explanation = ask("成品和自己充到底有什么区别？保一个月就是用一个月吗？")
    assert "质保" in explanation and "半成品" in explanation and "已有的账号" in explanation
    assert "https://example.com/2" in ask("第一家")


def test_ai_brand_switch_preserves_filters_without_the_previous_product(chat, provider):
    _, data, publish, _ = chat
    second = {
        **data["products"][0], "slug": "chatgpt-plus", "brand": "OpenAI", "display_name": "ChatGPT Plus",
        "brand_aliases": ["openai"], "search_aliases": ["plus"], "offer_count": 1, "comparable_offer_count": 1,
        "offers": [{**data["products"][0]["offers"][1], "id": 20, "original_name": "ChatGPT Plus", "price": 90}],
    }
    data["products"].append(second)
    data["offer_count"] += 1
    publish("2")
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro", "period": "one_month", "max_price": 110}]}
    ask("找一百一以内的克劳德月卡")
    provider["plan"] = {"action": "search", "searches": [{"inherit": True, "brand": "OpenAI"}]}
    reply = ask("条件不变，换成OpenAI的看看")
    assert "ChatGPT Plus" in reply and "¥90.00" in reply and "110" in reply
    assert "Claude Pro" not in reply


def test_search_can_also_explain_requested_terms(chat, provider):
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro", "delivery": "account"}], "topics": ["semi_finished"]}
    reply = ask("找点克劳德账号，也解释一下半成品是什么")
    assert "商家1" in reply and "半成品账号：" in reply


def test_compare_positions_cannot_invent_prices_or_compare_different_terms(chat, provider):
    ask("claude pro 月付")
    provider["plan"] = {"action": "compare", "positions": [1, 2]}
    reply = ask("前两个哪个划算呀")
    assert "¥60.00" in reply and "¥80.00" in reply and "第 1 项报价最低" in reply
    assert "https://example.com/2" in reply and "https://example.com/4" in reply
    ask("claude pro")
    mixed = ask("前两个比较看看")
    assert "不能直接按金额" in mixed


def test_comparison_does_not_recommend_an_unavailable_lower_price(chat, provider):
    _, data, publish, _ = chat
    data["products"][0]["offers"][1]["stock_status"] = "out_of_stock"
    publish("2")
    provider["plan"] = {"action": "compare", "searches": [
        {"product": "claude-pro", "period": "one_month", "stock": "out_of_stock"},
        {"product": "claude-pro", "period": "one_month"},
    ], "topics": ["period_warranty"]}
    reply = ask("比较克劳德月卡缺货和现货报价，质保和使用期是不是一回事")
    assert "¥60.00" in reply and "¥80.00" in reply and "报价最低" not in reply
    assert "不能直接按金额" in reply and "使用期限是" in reply


def test_compare_product_queries_and_missing_results(chat, provider):
    provider["plan"] = {"action": "compare", "searches": [
        {"product": "claude-pro", "period": "one_month"},
        {"product": "claude-pro", "period": "one_year"},
    ]}
    reply = ask("Claude Pro 按月和按年分别多少钱")
    assert "1 个月" in reply and "1 年" in reply and "不能直接按金额" in reply
    provider["plan"]["searches"][1]["max_price"] = 1
    assert "没有符合条件" in ask("按年不超过一元再比较")


def test_snapshot_changed_during_model_call_refreshes_numbered_choices(chat, provider):
    _, data, publish, _ = chat
    ask("claude pro")
    provider["plan"] = {"action": "compare", "positions": [1, 2]}
    def change():
        data["products"][0]["offers"][0]["price"] = 999
        publish("2")
    provider["callback"] = change
    reply = ask("第一和第二比较下")
    assert "报价已更新" in reply and "商品比较" not in reply
    assert "https://example.com/1" not in reply


def test_comparison_refresh_preserves_analysis_and_updates_numbered_choices(chat, provider):
    _, data, publish, _ = chat
    ask("Claude最高价")
    provider["plan"] = {"action": "compare", "positions": [1, 2]}
    def change():
        data["products"][0]["offers"][8]["price"] = 115
        publish("2")
    provider["callback"] = change
    reply = ask("对比前两项")
    assert "报价已更新" in reply and "最高报价 ¥120.00" in reply
    assert "商品比较" not in reply
    assert "https://example.com/8" in ask("第一家")


@pytest.mark.parametrize("api_style", ["chat_completions", "responses"])
def test_ai_selects_snapshot_analysis_from_a_natural_question(chat, provider, monkeypatch, api_style):
    monkeypatch.setattr(provider["config"], "api_style", api_style)
    provider["plan"] = {"action": "analyze", "metric": "mean", "searches": [{"product": "claude-pro", "period": "one_month", "access": "exclusive"}]}
    reply = ask("我想知道克劳德按月独享的市面开价大概是什么水平")
    assert "平均报价 ¥110.00" in reply and "2 条价格样本 / 2 家店" in reply
    assert "编造店铺" not in reply
    provider["plan"] = {"action": "analyze", "metric": "maximum", "searches": [{"inherit": True, "max_price": 110}]}
    reply = ask("这些里面不超过一百一的，给我看看顶价")
    assert "最高报价 ¥100.00" in reply and "¥120.00" not in reply
    context = provider["calls"][-1]["input" if api_style == "responses" else "messages"]
    assert json.loads(context[1]["content"])["previous_analysis_metric"] == "mean"


def test_ai_can_answer_global_popularity_without_requesting_a_brand(chat, provider):
    _, data, publish, _ = chat
    for offer in data["products"][0]["offers"]:
        offer["click_count"] = 7
    publish("2")
    provider["plan"] = {"action": "analyze", "metric": "popularity", "searches": [{}]}
    reply = ask("大家在这个网站更关注什么套餐啊")
    assert "Claude Pro：63 次累计点击" in reply and "不是销量" in reply
    assert "哪个品牌" not in reply and len(provider["calls"]) == 1
    provider["plan"] = {"action": "analyze", "metric": "mean", "searches": [{"product": "claude-pro", "period": "one_month"}]}
    reply = ask("排在第一的那个，按月付费的开价大概怎样")
    assert "平均报价 ¥70.00" in reply
    context = json.loads(provider["calls"][-1]["messages"][1]["content"])
    assert context["displayed_products"] == [{"position": 1, "slug": "claude-pro", "name": "Claude Pro"}]


def test_enabled_ai_interprets_analysis_conditions_before_rule_fallback(chat, provider):
    provider["plan"] = {"action": "analyze", "metric": "mean", "searches": [{"product": "claude-pro", "period": "one_month"}]}
    reply = ask("我想看每个月付费的Claude平均价格")
    assert "平均报价 ¥70.00" in reply and "平均报价 ¥110.00" in reply
    assert len(provider["calls"]) == 1


@pytest.mark.parametrize("plan", [
    {"action": "analyze", "metric": "execute_sql", "searches": [{}]},
    {"action": "search", "metric": "maximum", "searches": [{"product": "claude-pro"}]},
    {"action": "analyze", "metric": "mean", "searches": [], "positions": [1]},
    {"action": "search", "searches": [{"product": "nonexistent"}]},
    {"action": "search", "searches": [{"product": "claude-pro", "brand": "OpenAI"}]},
    {"action": "search", "searches": [{"product": "claude-pro", "min_price": 200, "max_price": 100}]},
    {"action": "search", "searches": [{"product": "claude-pro", "max_price": "NaN"}]},
    {"action": "search", "searches": [{"product": "claude-pro", "sql": "SELECT *"}]},
    {"action": "compare", "positions": [1, 1]},
    {"action": "detail", "positions": [8]},
    {"action": "search", "searches": [], "answer": "fake price"},
    {"action": "explain", "topics": ["invented"]},
])
def test_untrusted_plans_fail_to_local_search(chat, provider, plan):
    provider["plan"] = plan
    reply = ask("Claude Pro 月付")
    assert "AI 暂时不可用" in reply and "¥60.00" in reply
    assert "fake price" not in reply


@pytest.mark.parametrize("failure", ["timeout", "body", "tool"])
def test_provider_errors_do_not_leak_or_break_rule_search(chat, provider, caplog, failure):
    if failure == "timeout":
        provider["timeout"] = True
    elif failure == "body":
        provider["body"] = {"choices": "broken response with secret"}
    else:
        provider["tool"] = "run_sql"
    reply = ask("Claude Pro 月付")
    assert "¥60.00" in reply and "AI 暂时不可用" in reply
    assert "private provider" not in caplog.text and "with secret" not in caplog.text


def test_responses_api_and_unknown_request_clarification(chat, provider, monkeypatch):
    monkeypatch.setattr(provider["config"], "api_style", "responses")
    provider["plan"] = {"action": "clarify", "clarification": "product"}
    assert "哪个品牌或套餐" in ask("帮我挑个便宜的")
    provider["plan"] = {"action": "clarify", "clarification": "out_of_scope"}
    assert "查价、比较商品" in ask("给我写首诗")


def test_disabled_ai_shortcuts_and_sensitive_commands_never_call_model(chat, provider, monkeypatch):
    assert "自然语言价格助手" in ask("帮助")
    assert "自然语言价格助手" not in ask("帮助", channel="telegram")
    ask("claude pro")
    ask("下一页")
    ask("/bind invalid code extra")
    assert not provider["calls"]
    monkeypatch.setattr(provider["config"], "enabled", False)
    reply = ask("Claude Pro 月付")
    assert "¥60.00" in reply and not provider["calls"]


@pytest.mark.parametrize("message", [
    "<@123456> claude pro",
    "<@!123456> claude pro",
    "<@a1b2c3d4e5f60123456789abcdef01234> claude pro",
    "claude pro <@!a1b2c3d4e5f60123456789abcdef01234>",
    "<@bot_123-456> claude pro <@another_mention>",
    "@价格助手 claude pro",
])
def test_qq_mentions_do_not_pollute_exact_search_or_call_ai(chat, provider, message):
    reply = ask(message)
    assert "Claude Pro" in reply and "¥60.00" in reply
    assert "<@" not in reply and not provider["calls"]


@pytest.mark.parametrize("failure", ["timeout", "invalid_plan"])
def test_qq_mentions_are_removed_from_ai_and_fallback_search(chat, provider, failure):
    if failure == "timeout":
        provider["timeout"] = True
    else:
        provider["plan"] = {"action": "clarify", "searches": [{"brand": "Claude"}]}
    reply = ask("<@a1b2c3d4e5f60123456789abcdef01234> Claude Pro 月付")
    assert "AI 暂时不可用" in reply and "¥60.00" in reply
    assert "a1b2c3d4e5f60123456789abcdef01234" not in reply
    context = json.loads(provider["calls"][0]["messages"][1]["content"])
    assert context["request"] == "Claude Pro 月付"
    assert "a1b2c3d4e5f60123456789abcdef01234" not in json.dumps(provider["calls"])


def test_qq_mention_only_and_prefixed_commands_bypass_ai(chat, provider):
    assert "自然语言价格助手" in ask("<@bot_openid>")
    assert "自然语言价格助手" in ask("<@!bot_openid> 帮助")
    assert "绑定格式" in ask("<@bot_openid> /bind invalid code extra")
    assert not provider["calls"]


def test_other_channels_preserve_literal_mention_text(chat, monkeypatch):
    calls = []
    monkeypatch.setattr(snapshot_chat.snapshot_chat, "reply", lambda text, **kwargs: calls.append(text) or "ok")
    assert ask("<@literal> Claude", channel="telegram") == "ok"
    assert calls == ["<@literal> Claude"]


def test_ai_session_context_does_not_cross_groups_or_users(chat, provider):
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro", "max_price": 110}]}
    ask("帮我找克劳德预算110")
    provider["plan"] = {"action": "clarify", "clarification": "product"}
    for identity in (
        dict(sender_id="another-user", account_id="private-app", conversation_id="group:private-group"),
        dict(sender_id="private-user", account_id="private-app", conversation_id="group:another-group"),
        dict(sender_id="private-user", account_id="another-app", conversation_id="group:private-group"),
        dict(sender_id="private-user", account_id="private-app", conversation_id="c2c"),
    ):
        chat_commands.handle_chat_command("那再便宜一点", **identity)
        context = json.loads(provider["calls"][-1]["messages"][1]["content"])
        assert context["previous_query"] is None and context["displayed_quotes"] == []


def test_model_request_does_not_hold_search_lock(chat, provider):
    bot, _, _, _ = chat
    def while_waiting():
        assert bot.lock.acquire(blocking=False)
        bot.lock.release()
    provider["callback"] = while_waiting
    provider["plan"] = {"action": "search", "searches": [{"product": "claude-pro"}]}
    assert "商家1" in ask("帮我查个Claude会员")


def test_same_session_changed_during_model_call_rejects_stale_plan(chat, provider):
    ask("claude pro")
    provider["plan"] = {"action": "search", "searches": [{"inherit": True, "period": "one_month"}]}
    provider["callback"] = lambda: ask("重新搜索")
    assert "刚刚更新" in ask("那就按月的")


def test_request_limit_falls_back_without_more_model_calls(chat, provider):
    provider["plan"] = {"action": "clarify"}
    for _ in range(6):
        ask("帮我推荐一下")
    assert "AI 暂时不可用" in ask("Claude Pro 月付")
    assert len(provider["calls"]) == 6


def test_account_filter_also_works_when_ai_is_disabled(chat):
    bot, data, publish, _ = chat
    data["products"][0]["offers"][1]["delivery_type"] = "semi_finished_account"
    data["products"][0]["offers"][3]["delivery_type"] = "subscription_recharge"
    publish("2")
    reply = bot.reply("Claude Pro 只看账号 月付")
    assert "商家2" in reply and "商家4" not in reply


@pytest.mark.parametrize("url", ["http://remote.example/v1", "https://user:secret@example.com/v1", "https://example.com/v1?key=secret", "file:///private"])
def test_model_endpoint_requires_https_and_never_embeds_credentials(url):
    with pytest.raises(ValidationError):
        BotAISettingsUpdate(base_url=url)


def test_reply_worker_keeps_order_and_does_not_block_event_loop(monkeypatch):
    from extensions.bots import qq_gateway
    service = qq_gateway.QQGatewayService()
    entered, release = threading.Event(), threading.Event()
    sent = []
    def handle(**kwargs):
        if kwargs["raw_text"] == "first":
            entered.set()
            assert release.wait(5)
        return kwargs["raw_text"]
    monkeypatch.setattr(qq_gateway, "handle_chat_command", handle)
    monkeypatch.setattr(service.bot_client, "send_c2c_message", lambda **kwargs: sent.append(kwargs["text"]) or True)
    async def scenario():
        queue = asyncio.Queue(maxsize=2)
        worker = asyncio.create_task(service._reply_worker(queue, "app", "secret"))
        service._enqueue_message(queue, "first", "sender", "", "1")
        service._enqueue_message(queue, "second", "sender", "", "2")
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            # The gateway event loop can consume ACKs while this worker waits.
            assert not sent
            release.set()
            await asyncio.wait_for(queue.join(), 3)
            assert sent == ["first", "second"]
        finally:
            release.set()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
    asyncio.run(scenario())
