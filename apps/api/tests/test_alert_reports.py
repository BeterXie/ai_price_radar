from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.alert_reports import build_alert_report, unique_price_events
from app.services.notification_hub import create_price_change_event
from extensions.bots.formatter import render_qq_report, render_qq_team_reports, split_qq_messages
from extensions.bots.team_alerts import TeamLowPriceOffer


def event(id, title="同款 Team 5x 11月21日23点踢", price="20", currency="CNY"):
    return create_price_change_event(offer_id=id, product_name=title, shop_name=f"商家{id}",
                                    source_platform="ldxp", old_price=Decimal("30"), new_price=Decimal(price), currency=currency)


def quote(id, title="同款 Team 5x 11月21日23点踢", price=20, **kwargs):
    return {"id": id, "original_name": title, "shop_name": f"商家{id}", "price": price,
            "currency": "CNY", "stock_status": "in_stock", "stock_count": 1,
            "observed_at": "2026-11-21T06:00:00+00:00", **kwargs}


def snapshot(offers):
    return {"snapshot_id": "10", "published_at": "2026-11-21T06:01:00+00:00", "stale_offer_hours": 72,
            "products": [{"slug": "chatgpt-business", "offers": offers}]}


def test_same_title_keeps_cheapest_and_stable_tie_but_preserves_currency_and_specs():
    rows = [event(3, price="25"), event(2), event(1), event(4, currency="USD"),
            event(5, title="同款 Team 10x 11月21日23点踢"), event(6, price="19", currency="RMB")]
    assert {e.offer_id for e in unique_price_events(rows)} == {4, 5, 6}
    assert unique_price_events([event(2), event(1)])[0].offer_id == 1
    assert len(unique_price_events([event(1, title="Ｔｅａｍ  5X"), event(2, title="Team 5x")])) == 1


def test_report_filters_non_public_inconsistent_and_unavailable_changes_and_deduplicates():
    data = snapshot([quote(1, price=20), quote(2, price=18), quote(3, price=16, stock_status="out_of_stock"),
                     quote(4, title="Team 10x 11月21日23点踢", currency="USD"),
                     quote(5, title="Team 5x 11月21日13点踢"), quote(6, title="Team 5x 无结束时间")])
    report = build_alert_report(data, [event(1), event(2, price="18"), event(3, price="16"), event(999), event(4, price="19")],
                                previous_prices={i: (Decimal("30"), "CNY") for i in (1, 2, 3)})
    assert [r["offer_id"] for r in report["drops"]] == [2]
    assert [r["offer_id"] for r in report["team"]] == [2]
    assert report["drops"][0]["old_price"] == "30.00"
    assert report["team"][0]["ends_at"] == "2026-11-21T23:00:00+08:00"


def test_change_direction_keeps_the_cheapest_current_offer():
    low_rise = replace(event(2, price="10"), old_price=Decimal("8"), diff=Decimal("2"), is_drop=False, percent_change=25)
    report = build_alert_report(snapshot([quote(1), quote(2, price=10)]), [event(1), low_rise],
                                previous_prices={1: (Decimal("30"), "CNY"), 2: (Decimal("8"), "CNY")})
    assert report["drops"] == []
    assert [r["offer_id"] for r in report["rises"]] == [2]


def test_team_same_relative_title_with_different_end_dates_is_not_merged():
    report = build_alert_report(snapshot([quote(1, title="Team 5x 明晚23点踢", observed_at="2026-11-20T12:00:00Z"),
                                         quote(2, title="Team 5x 明晚23点踢")]), [])
    assert len(report["team"]) == 2


def test_messages_separate_items_and_link_to_latest_unpinned_boards():
    text = render_qq_report([event(1), event(2, price="18"), event(3, title="另一款")])
    assert "商家1" not in text and "商家2" in text
    assert "\n\n──────────\n\n" in text
    assert "/alerts?view=drops" in text and "/alerts/" not in text
    now = datetime.now(timezone.utc)
    offers = [TeamLowPriceOffer(1, "Team 5x 同名", "贵店", Decimal("20"), "", now + timedelta(hours=1)),
              TeamLowPriceOffer(2, "Team 5x 同名", "便宜店", Decimal("18"), "", now + timedelta(hours=1))]
    text = "\n".join(render_qq_team_reports(offers, detected_at=now))
    assert "贵店" not in text and "便宜店" in text
    assert "/alerts?view=team" in text


def test_byte_splitting_preserves_whole_product_blocks():
    blocks = [f"商品{i}\n" + "报价内容" * 40 for i in range(5)]
    chunks = split_qq_messages("\n\n──────────\n\n".join(blocks), limit=1200)
    assert len(chunks) > 1 and all(len(c.encode("utf-8")) <= 1200 for c in chunks)
    assert all(any(block in chunk for chunk in chunks) for block in blocks)


def test_long_team_pages_fit_one_request_and_recheck_expiry_between_requests():
    from extensions.bots.formatter import iter_qq_team_reports
    now = datetime.now(timezone.utc)
    offers = [TeamLowPriceOffer(i, f"Team 5x 商品{i} " + "完整商品标题" * 40, "商家" * 30,
                               Decimal("18"), "", now + timedelta(minutes=1)) for i in range(12)]
    clock = [now]
    pages = iter_qq_team_reports(offers, detected_at=now, current_time=lambda: clock[0])
    first = next(pages)
    assert len(first.encode("utf-8")) <= 3500
    assert "商品详情" in first and "/alerts?view=team" in first
    clock[0] = now + timedelta(minutes=2)
    assert list(pages) == []


def test_alerts_require_matching_previously_public_price_and_preserve_source_link():
    current = snapshot([quote(1, source_url="https://merchant.example/goods/1")])
    for baseline in ({}, {1: (Decimal("30"), "USD")}, {1: (Decimal("-1"), "CNY")}):
        assert build_alert_report(current, [event(1)], previous_prices=baseline)["drops"] == []
    report = build_alert_report(current, [event(1)], previous_prices={1: (Decimal("30"), "CNY")})
    assert report["drops"][0]["source_url"] == "https://merchant.example/goods/1"


def test_multiple_intra_import_changes_collapse_to_public_net_transition():
    report = build_alert_report(snapshot([quote(1, price=20)]), [event(1, price="25"), event(1, price="20")],
                                previous_prices={1: (Decimal("30"), "CNY")})
    assert len(report["drops"]) == 1 and report["drops"][0]["diff"] == "-10.00"


def test_non_deadline_or_ambiguous_team_dates_and_negated_head_titles_are_excluded():
    from app.services.team_rules import team_title_ends_at, is_head_car_title
    observed = datetime(2027, 3, 1, 1, tzinfo=timezone.utc)
    for title in ("Team 5x 今天18:00补货", "Team 5x 2月29日18:00到期", "Team 5x 截止11.20", "Team 5x 12:30 AM 到期"):
        assert team_title_ends_at(title, observed_at=observed) is None
    assert not is_head_car_title("Team 5x 非首车 今天23点踢")
    assert not is_head_car_title("Team 5x 非第一车 今天23点踢")


def test_invalid_chinese_date_does_not_abort_other_alerts():
    current = snapshot([quote(1, title="Team 5x 十十月二十日23点踢"), quote(2)])
    report = build_alert_report(current, [event(2)], previous_prices={2: (Decimal("30"), "CNY")})
    assert [row["offer_id"] for row in report["team"]] == [2]
    assert len(report["drops"]) == 1


def test_public_report_builder_does_not_require_bot_extensions(monkeypatch):
    monkeypatch.setitem(sys.modules, "extensions", None)
    assert len(build_alert_report(snapshot([quote(1)]), [])["team"]) == 1


def test_telegram_team_batches_check_expiration_before_each_http_message():
    from extensions.bots.formatter import iter_telegram_team_reports
    now = datetime.now(timezone.utc)
    clock = [now]
    offers = [TeamLowPriceOffer(i, f"Team {i} " + "<&>" * 200, "商家", Decimal("18"), "", now + timedelta(seconds=1)) for i in range(12)]
    pages = iter_telegram_team_reports(offers, detected_at=now, current_time=lambda: clock[0])
    assert len(next(pages)) < 4000
    clock[0] += timedelta(seconds=2)
    assert list(pages) == []
