from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from test_snapshot_chat import chat
from extensions.bots import chat_commands, snapshot_chat


def replace_offers(data, offers):
    data['products'][0].update(offers=offers, offer_count=len(offers), comparable_offer_count=sum(o['is_comparable'] for o in offers))
    data['offer_count'] = len(offers)


def test_screenshot_questions_work_without_a_configured_model(chat):
    bot, _, _, _ = chat
    assert '最低' in chat_commands.handle_chat_command('claude', sender_id='alice')
    maximum = chat_commands.handle_chat_command('claude最高', sender_id='alice')
    assert '最高报价 ¥130.00' in maximum and 'https://example.com/9' in maximum
    assert 'https://example.com/9' in bot.reply('第一家', sender_id='alice')
    average = chat_commands.handle_chat_command('我想看claude平均价格', sender_id='alice')
    assert '平均报价 ¥70.00' in average and '中位数 ¥70.00' in average
    assert '平均报价 ¥110.00' in average and '平均报价 ¥120.00' in average
    assert '匹配 9 条店铺报价 / 9 家店' in average
    assert '1 个月' in average and '1 年' in average and '真实成交' not in average


def test_statistics_keep_other_shops_and_use_the_latest_duplicate(chat):
    bot, data, publish, _ = chat
    base = {**data['products'][0]['offers'][0], 'item_fingerprint': 'same-item', 'service_period': 'one_month', 'account_access': 'exclusive'}
    offers = [{**base, 'id': i, 'shop_token': f'shop-{i}', 'shop_name': f'店铺{i}', 'price': price} for i, price in enumerate((100, 120, 300), 1)]
    offers.extend([
        {**offers[1], 'id': 4, 'price': 20, 'observed_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()},
        {**base, 'id': 5, 'shop_token': 'bait', 'price': 99999, 'is_trusted_price': False},
        {**base, 'id': 6, 'shop_token': 'out', 'price': 600, 'stock_status': 'out_of_stock'},
        {**base, 'id': 7, 'shop_token': 'usd', 'price': 2, 'currency': 'USD'},
        {**base, 'id': 8, 'shop_token': 'stale', 'price': 10, 'observed_at': (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()},
        {**base, 'id': 9, 'shop_token': 'missing', 'price': None},
    ])
    replace_offers(data, offers)
    publish('2')
    reply = bot.reply('Claude Pro 月付平均价', sender_id='alice')
    assert '平均报价 ¥173.33' in reply and '中位数 ¥120.00' in reply
    assert '3 条价格样本 / 3 家店' in reply
    for excluded in ('99999.00', '600.00', '20.00 @', '10.00', 'USD 2.00'):
        assert excluded not in reply
    assert '最高报价 ¥300.00' in bot.reply('最高价', sender_id='alice')
    assert '最低 ¥100.00 · 最高 ¥300.00 · 价差 ¥200.00' in bot.reply('价差', sender_id='alice')


def test_delivery_period_access_and_currency_are_not_averaged_together(chat):
    bot, data, publish, _ = chat
    base = {**data['products'][0]['offers'][0], 'account_access': 'exclusive', 'service_period': 'one_month'}
    offers = [
        {**base, 'id': 1, 'price': 10},
        {**base, 'id': 2, 'price': 20, 'delivery_type': 'semi_finished_account'},
        {**base, 'id': 3, 'price': 30, 'delivery_type': 'subscription_recharge'},
        {**base, 'id': 4, 'price': 40, 'service_period': 'one_year'},
        {**base, 'id': 5, 'price': 50, 'account_access': 'unknown'},
        {**base, 'id': 6, 'price': 60, 'currency': 'USD'},
    ]
    replace_offers(data, offers)
    publish('2')
    reply = bot.reply('Claude Pro平均价', sender_id='alice')
    assert '共 5 组' in reply and '仅 1 条样本' in reply
    for price in (10, 20, 30, 40, 50):
        assert f'平均报价 ¥{price:.2f}' in reply
    assert '平均报价 ¥30.00 · 中位数 ¥30.00' in reply  # Recharge group, never an overall mean.
    usd = bot.reply('Claude Pro美元均价')
    assert '平均报价 USD 60.00' in usd and '¥' not in usd and '· USD' in usd
    accounts = bot.reply('Claude Pro账号均价')
    assert '半成品' in accounts and '官方直充' not in accounts


def test_inventory_counts_missing_and_untrusted_prices_without_inventing_sales(chat):
    bot, data, publish, _ = chat
    offers = data['products'][0]['offers']
    offers[0].update(stock_status='out_of_stock')
    offers[1].update(stock_status='unknown', stock_count=None)
    offers[2].update(stock_count=None, price=None)
    offers[3].update(is_trusted_price=False)
    publish('2')
    stock = bot.reply('Claude Pro库存')
    assert '有货 7 条 · 已售罄 1 条 · 库存未知 1 条' in stock
    assert '1 条未注明库存件数' in stock and '不能证明销量或成交' in stock
    count = bot.reply('Claude Pro有多少条报价')
    assert '覆盖 1 个套餐' in count and 'Claude Pro：9 条报价' in count
    shops = bot.reply('Claude Pro有多少家店', sender_id='alice')
    assert '/ 9 家店' in shops and '第 1/2 页' in shops
    assert '第 2/2 页' in bot.reply('下一页', sender_id='alice')


def test_statistics_followups_preserve_filters_and_can_return_to_quotes(chat):
    bot, _, _, _ = chat
    bot.reply('Claude Pro平均价', sender_id='alice')
    monthly = bot.reply('只看月付', sender_id='alice')
    assert '平均报价' in monthly and '1 年' not in monthly
    budget = bot.reply('110元以内', sender_id='alice')
    assert '平均报价 ¥100.00' in budget and '¥120.00' not in budget
    assert '当前统计页没有报价序号' in bot.reply('第一家', sender_id='alice')
    assert '最低在售' in bot.reply('查看报价', sender_id='alice')
    assert 'https://example.com/2' in bot.reply('第一家', sender_id='alice')
    assert '请告诉我商品' in bot.reply('平均价', sender_id='bob')


def test_statistics_refresh_numbered_highest_quotes_after_snapshot_change(chat):
    bot, data, publish, _ = chat
    bot.reply('Claude最高价', sender_id='alice')
    data['products'][0]['offers'][8]['price'] = 115
    publish('2')
    refreshed = bot.reply('第一家', sender_id='alice')
    assert '报价已更新' in refreshed and '最高报价 ¥120.00' in refreshed
    assert 'https://example.com/8' in bot.reply('第一家', sender_id='alice')


@pytest.mark.parametrize('question, fragment', [
    ('Claude最近真实成交价格', '没有订单、支付金额'),
    ('平均成交价是多少', '无法提供真实成交价'),
    ('这款商品销量多少', '无法提供真实成交价'),
    ('Claude过去7天平均报价', '不能据此计算过去几天'),
    ('Claude价格走势', '不能据此计算过去几天'),
])
def test_missing_transaction_or_historical_evidence_is_explicit(chat, monkeypatch, question, fragment):
    bot, _, _, _ = chat
    bot.reply('Claude Pro', sender_id='alice')
    monkeypatch.setattr(snapshot_chat.price_assistant, 'plan', lambda *args, **kwargs: pytest.fail('Unsupported evidence must not be invented by the model'))
    reply = bot.reply(question, sender_id='alice', use_ai=True)
    assert fragment in reply and '¥' not in reply
    assert 'https://example.com/1' in bot.reply('第一家', sender_id='alice')


def test_analysis_no_valid_prices_and_data_freshness(chat):
    bot, data, publish, _ = chat
    for offer in data['products'][0]['offers']:
        offer['is_trusted_price'] = False
    publish('2')
    reply = bot.reply('分析一下Claude Pro')
    assert '没有符合条件的有效价格样本' in reply and '平均报价 ¥' not in reply
    updated = bot.reply('Claude Pro数据更新时间')
    assert '快照 #2' in updated and '最新观测' in updated and '最早观测' in updated


def test_popularity_uses_actual_clicks_and_global_question_clears_subject(chat):
    bot, data, publish, _ = chat
    for offer in data['products'][0]['offers']:
        offer['click_count'] = 1
    first = data['products'][0]
    second = {**first, 'slug': 'chatgpt-plus', 'brand': 'OpenAI', 'display_name': 'ChatGPT Plus', 'brand_aliases': ['openai'], 'search_aliases': ['plus'], 'offer_count': 1, 'comparable_offer_count': 1,
              'offers': [{**first['offers'][0], 'id': 20, 'original_name': 'Plus 月付', 'click_count': 100}]}
    data['products'].append(second)
    data['offer_count'] += 1
    publish('2')
    bot.reply('claude', sender_id='alice')
    reply = bot.reply('本站热门商品', sender_id='alice')
    assert 'ChatGPT Plus：100 次累计点击' in reply and 'Claude Pro：9 次累计点击' in reply
    assert reply.index('ChatGPT Plus') < reply.index('Claude Pro')
    assert '不是销量' in reply and '不是最近几天' in reply
    selected = bot.reply('第一个', sender_id='alice')
    assert 'ChatGPT Plus' in selected and 'Claude Pro' not in selected
    assert '平均报价 ¥50.00' in bot.reply('平均价', sender_id='alice')
    assert 'ChatGPT Plus' in bot.reply('本站有哪些商品')


def test_catalog_includes_visible_products_without_current_quotes(chat):
    bot, data, publish, _ = chat
    replace_offers(data, [])
    publish('2')
    assert 'Claude Pro · Claude：0 条报价' in bot.reply('本站有哪些商品')


def test_absent_or_zero_click_data_never_fabricates_a_popularity_ranking(chat):
    bot, data, publish, _ = chat
    missing = bot.reply('本站热门商品')
    assert '未提供完整的站内点击数据' in missing and '不能用报价数量' in missing
    for offer in data['products'][0]['offers']:
        offer['click_count'] = 0
    publish('2')
    assert '尚无有效点击记录' in bot.reply('本站热门商品')


@pytest.mark.parametrize('clicks', [-1, True, '100'])
def test_invalid_click_evidence_is_rejected(chat, clicks):
    bot, data, publish, _ = chat
    data['products'][0]['offers'][0]['click_count'] = clicks
    publish('2')
    assert '无效点击统计' in bot.reply('热门商品')
