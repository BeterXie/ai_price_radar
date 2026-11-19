from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.database import Base
from app.models import CatalogSnapshot, NotificationOutbox, Offer, Product, RawProduct, Shop, SystemSetting, User, UserBotBinding, UserProductSubscription
from app.services.notification_hub import create_price_change_event, dispatch_price_changes
from extensions.bots import dispatcher
from extensions.bots.formatter import (
    render_qq_report,
    render_qq_team_reports,
    render_telegram_report,
    render_telegram_team_report,
    split_qq_messages,
)
from extensions.bots.team_alerts import BEIJING, TeamLowPriceOffer, collect_team_low_price_offers, is_team_account_title, is_head_car_title, team_title_ends_at


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def deliveries(monkeypatch):
    sent = SimpleNamespace(qq=[], telegram=[])

    class FakeQQ:
        is_configured = True

        def __init__(self, **kwargs):
            pass

        def send_c2c_message(self, target_id, text, **kwargs):
            sent.qq.append((target_id, text))
            return True

    class FakeTelegram:
        is_configured = True

        def send_admin_message(self, text):
            sent.telegram.append(text)
            return True

    monkeypatch.setattr(dispatcher, "QQBotClient", FakeQQ)
    monkeypatch.setattr(dispatcher, "TelegramBotClient", FakeTelegram)
    return sent


def add_snapshot(db):
    snapshot = CatalogSnapshot(published_at=datetime.now(timezone.utc))
    db.add(snapshot)
    db.flush()
    return snapshot


def add_offer(db, snapshot, *, title=None, price="20.00", slug="chatgpt-business", **changes):
    if title is None:
        deadline = (datetime.now(timezone.utc) + timedelta(hours=3)).astimezone(BEIJING)
        title = f"【二车】Team 5x /{deadline:%Y-%m-%d %H:%M}踢/2fa-G邮箱"
    product = db.query(Product).filter_by(slug=slug).first()
    if product is None:
        product = Product(slug=slug, platform="OpenAI", display_name=slug)
        db.add(product)
    shop = Shop(token=f"shop-{db.query(Shop).count()}", name="测试商家", source_url="https://merchant.example")
    db.add(shop)
    db.flush()
    raw = RawProduct(shop_id=shop.id, source_product_key="team", original_name=title, source_url="https://merchant.example/goods/team?a=1&b=2")
    db.add(raw)
    db.flush()
    offer = Offer(
        product_id=product.id, shop_id=shop.id, raw_product_id=raw.id,
        snapshot_id=snapshot.id, price=Decimal(price), currency="CNY", stock_status="in_stock", stock_count=1,
    )
    for key, value in changes.items():
        setattr(offer, key, value)
    db.add(offer)
    db.flush()
    return offer


@pytest.mark.parametrize("title", [
    "【二车】Team 5x/23点踢/2fa-G邮箱/质保空间不炸",
    "Team 真头车｜不踢人｜500~1000刀10X额度",
    "ChatGPT Team 5× 成品号", "Team 10✖️ 成品号", "Team 5倍成品号", "Team 第2车",
    "ChatGPT Team 5x 成品号（附使用教程）",
    "【二车】10Xteam /账密2fa /22点30踢/质保炸车封号1个小时",
    "5x team /2车/19号凌晨1点踢/不保降智 限流/发2fa",
    "二车晚上 23点59 踢 新10x team【 gm邮箱 700-1000刀】",
    "Team 5x 真二车｜19号早上八点踢｜发账密2fa",
    "Ｔｅａｍ ５Ｘ／发账密",
    "【二车】Team /23点踢",
])
def test_matches_requested_team_title_variants(title):
    assert is_team_account_title(title)


@pytest.mark.parametrize("title", [
    "Cursor Team 5x 成品号", "Claude Team 5x", "Gemini Team 5x",
    "【高质量-已接马】free家宽gmail谷歌注册-账密2fa-可用5xteam车子号",
    "icloud邮箱的已接马free（高权重，5xteam开车防炸车）",
    "5xteam 底号 可升级", "普号，可用5xteam车子号", "Team 5x 不含会员", "ChatGPT Plus 月卡", "steam 5x",
    "Team 1x 第十二车", "Team 1x 第12车", "ChatGPT 基础账号 2FA，可用于 Team 5x，无订阅",
    "普通账号 用于 Team 5x", "免费账号 用于 Team 5x", "Team 15x", "Team 100x",
    "Team 2.5倍", "Team 0.5x", "Team 1.10x", "Team 5x 开通教程",
])
def test_excludes_other_products_and_team_upgrade_accounts(title):
    assert not is_team_account_title(title)


@pytest.mark.parametrize('title,expected', [
    ('【二车】Team 5x /23点踢', '2026-11-19 23:00'),
    ('Team 5x 21.30踢', '2026-11-19 21:30'),
    ('二车晚上 23点59 踢 新10x team', '2026-11-19 23:59'),
    ('头车质保15分钟降智20日凌晨1点踢 新10x team【gm邮箱700-1000刀】', '2026-11-20 01:00'),
    ('真头车 凌晨1:30踢人 10x team', '2026-11-20 01:30'),
    ('Team 5x 20号早上八点踢', '2026-11-20 08:00'),
    ('Team 5x 明早八点半踢', '2026-11-20 08:30'),
    ('Team 5x 今日凌晨1点踢', '2026-11-19 01:00'),
    ('Team 5x 明天上午8:30下车', '2026-11-20 08:30'),
    ('Team 5x 11月20日下午三点三十分结束', '2026-11-20 15:30'),
    ('Team 5x 11/20 01:30到期', '2026-11-20 01:30'),
    ('Team 5x 2026-11-20 24:00踢', '2026-11-21 00:00'),
    ('Team 5x 今晚12点踢', '2026-11-20 00:00'),
    ('Team 5x 19号16点开车 20号早8点踢', '2026-11-20 08:00'),
    ('Team 5x 11.20 01:30踢', '2026-11-20 01:30'),
    ('Team 5x 有效至2026年11月20日凌晨2点', '2026-11-20 02:00'),
    ('Team 5x 十二月二十日晚上八点结束', '2026-12-20 20:00'),
    ('Team 5x 二〇二六年十月二十日晚上八点结束', '2026-10-20 20:00'),
    ('Team 5x 今天中午一点结束', '2026-11-19 13:00'),
    ('Team 5x 今天中午十二点结束', '2026-11-19 12:00'),
    ('Team 头车 昨天晚上八点结束', '2026-11-18 20:00'),
    ('Team 头车 昨晚八点结束', '2026-11-18 20:00'),
    ('Team 头车 前天23点踢', '2026-11-17 23:00'),
    ('Team 头车 截止11.20 20:00', '2026-11-20 20:00'),
    ('Team 头车 截止11.20，20:00踢', '2026-11-20 20:00'),
    ('Team 头车 截止11.20｜20:00踢', '2026-11-20 20:00'),
    ('Team 头车 截止【11.20】20:00踢', '2026-11-20 20:00'),
])
def test_title_end_time_variants(title, expected):
    observed = datetime(2026, 11, 19, 20, 0, tzinfo=BEIJING)
    assert team_title_ends_at(title, observed_at=observed).strftime('%Y-%m-%d %H:%M') == expected


@pytest.mark.parametrize('title', [
    '头车 Team 5x 不踢人', 'Team 5x 质保1小时', 'Team 5x 23点开车',
    'Team 5x 25:30踢', 'Team 5x 24:30踢', 'Team 5x 23:70踢',
    'Team 5x 11点踢或23点踢', 'Team 5x 2月30日10点踢',
    '头车 Team 5x 特价23.50元', 'Team 5x 11.20 福利', 'Team 5x 上周五23点踢',
    'Team 5x 去年12月20日23点踢', 'Team 5x 本月1号23点踢',
    'Team 5x 11.20踢或23:00踢',
])
def test_missing_invalid_and_ambiguous_end_times_are_not_guessed(title):
    assert team_title_ends_at(title, observed_at=datetime(2026, 11, 19, 20, tzinfo=BEIJING)) is None


def test_day_only_titles_resolve_month_boundaries_and_old_relative_titles_stay_old():
    observed = datetime(2026, 12, 31, 20, tzinfo=BEIJING)
    assert team_title_ends_at('头车 Team 5x 1号凌晨1点踢', observed_at=observed) == datetime(2027, 1, 1, 1, tzinfo=BEIJING)
    assert team_title_ends_at('二车 Team 5x 明早8点踢', observed_at=observed) == datetime(2027, 1, 1, 8, tzinfo=BEIJING)
    assert team_title_ends_at('二车 Team 5x 31号23点踢', observed_at=datetime(2027, 1, 1, tzinfo=BEIJING)) == datetime(2026, 12, 31, 23, tzinfo=BEIJING)


def test_head_price_limit_and_expiry_use_actual_current_time(db):
    snapshot = add_snapshot(db)
    now = datetime.now(timezone.utc)
    future = (now + timedelta(hours=2)).astimezone(BEIJING).strftime('%Y-%m-%d %H:%M')
    past = (now - timedelta(hours=1)).astimezone(BEIJING).strftime('%Y-%m-%d %H:%M')
    head = add_offer(db, snapshot, title=f'真头车 Team 5x {future}踢', price='30')
    second = add_offer(db, snapshot, title=f'二车 Team 5x {future}踢', price='20')
    for title, price in [(f'头车 Team 5x {future}踢','30.01'), (f'二车 Team 5x {future}踢','20.01'),
                         (f'非头车 Team 5x {future}踢','25'), (f'头车 Team 5x {past}踢','10'),
                         ('头车 Team 5x 不踢人','10')]:
        add_offer(db, snapshot, title=title, price=price)
    db.commit()
    offers = collect_team_low_price_offers(db, snapshot, now=now)
    assert [offer.offer_id for offer in offers] == [second.id, head.id]
    assert offers[-1].is_head_car and not offers[0].is_head_car
    assert all(offer.ends_at > now for offer in offers)
    assert collect_team_low_price_offers(db, snapshot, now=offers[0].ends_at) == []
    qq = '\n'.join(render_qq_team_reports(offers, detected_at=now))
    tg = render_telegram_team_report(offers, detected_at=now)
    for report in (qq, tg):
        assert '头车≤¥30' in report and '结束时间' in report
        assert f'https://ai.pricememo.cn/offers/{head.id}' in report


def test_delivery_rechecks_expiry_after_collection(db, deliveries, monkeypatch):
    snapshot = add_snapshot(db)
    add_offer(db, snapshot)
    user = User(email='late@example.com')
    db.add(user)
    db.flush()
    db.add(UserBotBinding(user_id=user.id, target_id='late-user', notify_price_drop=True))
    db.commit()
    assert collect_team_low_price_offers(db, snapshot)
    monkeypatch.setattr(dispatcher, 'utcnow', lambda: datetime.now(timezone.utc) + timedelta(hours=4))
    dispatch_price_changes([], db_session=db, snapshot_id=snapshot.id)
    assert deliveries.qq == deliveries.telegram == []


@pytest.mark.parametrize('expire_after', ['price_report', 'first_team_page'])
def test_queued_team_pages_expire_while_earlier_messages_are_sending(db, deliveries, monkeypatch, expire_after):
    snapshot = add_snapshot(db)
    for _ in range(9):
        offer = add_offer(db, snapshot)
    user = User(email='queued@example.com')
    db.add(user)
    db.flush()
    db.add(UserBotBinding(user_id=user.id, target_id='queued-user', notify_price_drop=True))
    db.commit()
    now = datetime.now(timezone.utc)
    clock = [now]
    monkeypatch.setattr(dispatcher, 'utcnow', lambda: clock[0])
    original_send = dispatcher.QQBotClient.send_c2c_message

    def send_and_advance(self, target, message, **kwargs):
        result = original_send(self, target, message, **kwargs)
        clock[0] = now + timedelta(hours=4)
        return result

    monkeypatch.setattr(dispatcher.QQBotClient, 'send_c2c_message', send_and_advance)
    events = [create_price_change_event(offer_id=offer.id, product_name='Team 5x', shop_name='Shop',
              source_platform='ldxp', old_price=Decimal('30'), new_price=Decimal('20'))] if expire_after == 'price_report' else []
    dispatch_price_changes(events, db_session=db, snapshot_id=snapshot.id)
    assert len(deliveries.qq) == 1
    assert ('OpenAI Team ≤¥20 提醒' in deliveries.qq[0][1]) == (expire_after == 'first_team_page')


def test_collects_only_current_public_in_stock_cny_offers_at_or_below_20(db):
    old = add_snapshot(db)
    add_offer(db, old, price="1.00")
    current = add_snapshot(db)
    at_limit = add_offer(db, current)
    cheaper = add_offer(db, current, price="10.00", slug="chatgpt-access-service")
    cheaper.source_url = "https://merchant.example/goods/current"
    rmb = add_offer(db, current, price="19.99", currency="RMB", stock_count=None)
    for changes in [
        {"price": "20.01"}, {"price": "0"}, {"price": "-1"},
        {"currency": "USD"}, {"stock_status": "out_of_stock"}, {"stock_status": "unknown"}, {"stock_count": 0},
        {"active": False}, {"approved": False}, {"hidden_reason": "人工隐藏"},
        {"observed_at": datetime.now(timezone.utc) - timedelta(hours=get_settings().stale_offer_hours + 1)},
        {"title": "Cursor Team 5x"}, {"title": "free成品 可用5xteam车子号"},
        {"slug": "claude-team"}, {"slug": "chatgpt-account"},
    ]:
        add_offer(db, current, **changes)
    hidden_shop = add_offer(db, current)
    hidden_shop.shop.is_visible = False
    closed_shop = add_offer(db, current)
    closed_shop.shop.status = "closed"
    hidden_product = add_offer(db, current, slug="chatgpt-hidden")
    hidden_product.product.is_visible = False
    db.commit()

    offers = collect_team_low_price_offers(db, current)
    assert [o.offer_id for o in offers] == [cheaper.id, rmb.id, at_limit.id]
    assert offers[0].product_url == "https://merchant.example/goods/current"
    assert offers[-1].product_url == "https://merchant.example/goods/team?a=1&b=2"
    current.published_at = None
    assert collect_team_low_price_offers(db, current) == []


def test_reports_use_beijing_snapshot_time_and_exact_site_offer_link():
    detected_at = datetime(2026, 11, 18, 18, 45, 56, tzinfo=timezone.utc)
    event = create_price_change_event(
        offer_id=1, product_name="Team <5x>", shop_name="A&B", source_platform="ldxp",
        old_price=Decimal("30.00"), new_price=Decimal("20.00"),
        product_url='https://merchant.example/goods/1?a=1&b="2"',
    )
    qq = render_qq_report([event], detected_at=detected_at)
    tg = render_telegram_report([event], detected_at=detected_at)
    assert "商品详情: https://ai.pricememo.cn/offers/1" in qq
    assert 'href="https://ai.pricememo.cn/offers/1"' in tg
    assert "merchant.example" not in qq + tg
    for report in (qq, tg):
        assert "2026-11-19 02:45:56（北京时间 UTC+8）" in report
    assert render_qq_report([event], detected_at=detected_at.replace(tzinfo=None)) == qq


def test_team_reports_keep_all_results_and_escape_telegram_fields():
    offers = [TeamLowPriceOffer(i, f"Team <5x> {i}", "A&B", Decimal("20"), f"https://merchant.example/{i}?a=1&b=2") for i in range(19)]
    detected_at = datetime(2026, 11, 18, 13, 45, 56, tzinfo=timezone.utc)
    reports = render_qq_team_reports(offers, detected_at=detected_at)
    assert len(reports) == 3
    assert sum(report.count("现价: ¥20.00") for report in reports) == 19
    assert "（3/3）" in reports[-1]
    assert "2026-11-18 21:45:56（北京时间 UTC+8）" in reports[-1]
    for offer in offers:
        assert f"https://ai.pricememo.cn/offers/{offer.offer_id}" in "\n".join(reports)
    tg = render_telegram_team_report(offers, detected_at=detected_at)
    assert "Team &lt;5x&gt; 0" in tg and "A&amp;B" in tg
    assert 'href="https://ai.pricememo.cn/offers/18"' in tg
    assert "merchant.example" not in tg + "\n".join(reports)
    assert "https://example.com/offers/18" in render_qq_team_reports(offers, detected_at=detected_at, site_base_url="https://example.com/")[-1]


def test_qq_messages_split_long_names_and_links_before_delivery():
    long_offer = TeamLowPriceOffer(
        1,
        "Team 5x " + "商品名" * 1200,
        "测试商家",
        Decimal("20"),
        "https://merchant.example/" + "x" * 1200,
    )
    reports = render_qq_team_reports([long_offer], detected_at=datetime.now(timezone.utc))
    chunks = split_qq_messages(reports[0], limit=3500)
    assert len(chunks) > 1
    assert all(0 < len(chunk.encode("utf-8")) <= 3500 for chunk in chunks)
    assert "现价: ¥20.00" in "\n".join(chunks)
    assert "https://ai.pricememo.cn/offers/1" in "\n".join(chunks)
    tg = render_telegram_team_report([long_offer], detected_at=datetime.now(timezone.utc))
    assert "…" in tg and len(tg) < 4000
    oversized_link = "https://merchant.example/" + "x" * 5000
    assert "链接过长" in split_qq_messages(oversized_link)[0]


def test_each_published_snapshot_alerts_even_without_price_changes(db, deliveries):
    first = add_snapshot(db)
    offer = add_offer(db, first)
    for index, (active, drop) in enumerate([(True, True), (True, False), (False, True)]):
        user = User(email=f"user{index}@example.com")
        db.add(user)
        db.flush()
        db.add(UserBotBinding(user_id=user.id, target_id=f"qq-{index}", is_active=active, notify_price_drop=drop))
    db.commit()

    dispatch_price_changes([], db_session=db, snapshot_id=first.id)
    second = add_snapshot(db)
    offer.snapshot_id = second.id
    db.commit()
    dispatch_price_changes([], db_session=db, snapshot_id=second.id)

    assert [target for target, _ in deliveries.qq] == ["qq-0", "qq-0"]
    assert len(deliveries.telegram) == 2
    for _, report in deliveries.qq:
        assert "OpenAI Team ≤¥20 提醒" in report and "现价: ¥20.00" in report
        assert "价格变动提醒" not in report

    # Old/unpublished snapshots and empty matches must not send stale alerts.
    dispatch_price_changes([], db_session=db, snapshot_id=first.id)
    draft = CatalogSnapshot()
    db.add(draft)
    db.commit()
    dispatch_price_changes([], db_session=db, snapshot_id=draft.id)
    offer.price = Decimal("20.01")
    db.commit()
    dispatch_price_changes([], db_session=db, snapshot_id=second.id)
    assert len(deliveries.qq) == len(deliveries.telegram) == 2


def test_bot_disabled_also_suppresses_snapshot_threshold_alerts(db, deliveries):
    snapshot = add_snapshot(db)
    add_offer(db, snapshot)
    db.add(SystemSetting(key="bot_enabled", value="false"))
    db.commit()
    dispatch_price_changes([], db_session=db, snapshot_id=snapshot.id)
    assert deliveries.qq == deliveries.telegram == []


@pytest.mark.parametrize("failure", ["sql", "stale_snapshot"])
def test_team_query_failure_or_stale_snapshot_preserves_price_changes(db, deliveries, monkeypatch, failure):
    snapshot = add_snapshot(db)
    offer = add_offer(db, snapshot)
    user = User(email="subscriber@example.com")
    db.add(user)
    db.flush()
    db.add(UserProductSubscription(user_id=user.id, product_slug="chatgpt-business", notify_email=True, notify_bot=False))
    db.add(UserBotBinding(user_id=user.id, target_id="qq-user", notify_price_drop=True))
    db.commit()
    if failure == "sql":
        def failed_query(session, _snapshot):
            session.execute(text("SELECT * FROM deliberately_missing_table"))
        monkeypatch.setattr(dispatcher, "collect_team_low_price_offers", failed_query)
    else:
        add_snapshot(db)
        db.commit()
    event = create_price_change_event(
        offer_id=offer.id, product_name="Team 5x", shop_name="测试商家", source_platform="ldxp",
        old_price=Decimal("30"), new_price=Decimal("20"), product_slug="chatgpt-business",
    )
    dispatch_price_changes([event], db_session=db, snapshot_id=snapshot.id)
    assert db.query(NotificationOutbox).filter_by(event_type="price_subscription_alert").count() == 1
    assert len(deliveries.qq) == len(deliveries.telegram) == 1
    assert "价格变动提醒" in deliveries.qq[0][1]
    assert "Team ≤" not in deliveries.qq[0][1]
