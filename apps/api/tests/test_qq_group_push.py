import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.database import Base
from app.models import CatalogSnapshot, QQGroupSubscription, SystemSetting
from app.services.notification_hub import create_price_change_event, dispatch_price_changes
from extensions.bots import group_push, dispatcher, qq_gateway
from extensions.bots.formatter import render_qq_group_digest
from extensions.bots.qq_bot import QQBotClient
from extensions.bots.team_alerts import TeamLowPriceOffer


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(group_push, "SessionLocal", factory)
    monkeypatch.setenv("QQ_BOT_APP_ID", "bot-a")
    monkeypatch.setenv("QQ_BOT_APP_SECRET", "secret-a")
    monkeypatch.delenv("QQ_BOT_BRIDGE_URL", raising=False)
    sent, errors, sleeps = [], [], []
    clock = [datetime(2026, 11, 21, 7, tzinfo=timezone.utc)]
    state = [{"allow_proactive_msg": True}]
    class FakeQQ:
        def __init__(self, app_id=None, app_secret=None):
            self.app_id, self.app_secret = app_id, app_secret
            self.last_group_error_code = None
        def get_group_state(self, group):
            return state[0]
        def prepare_send(self, **kwargs):
            return True
        def send_group_message(self, group, message):
            self.last_group_error_code = errors.pop(0) if errors else None
            sent.append((self.app_id, group, message))
            return self.last_group_error_code is None
    monkeypatch.setattr(group_push, "QQBotClient", FakeQQ)
    monkeypatch.setattr(qq_gateway, "_is_bot_enabled", lambda: True)
    monkeypatch.setattr(group_push, "utcnow", lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += timedelta(seconds=seconds)
    monkeypatch.setattr(group_push.time, "sleep", sleep)
    with factory() as db:
        snapshot = CatalogSnapshot(published_at=clock[0])
        db.add(snapshot)
        db.commit()
    yield factory, sent, errors, state, clock, sleeps
    engine.dispose()


def group_row(factory, group="group-a", app_id="bot-a"):
    with factory() as db:
        return db.scalar(select(QQGroupSubscription).where(QQGroupSubscription.app_id == app_id,
                                                          QQGroupSubscription.group_openid == group))


def native(event, second=1, *, group="group-a", app_id="bot-a"):
    group_push.apply_group_event(app_id, event, {"group_openid": group, "timestamp": 1795244400 + second})


def command(text="开启群推送", role="owner", group="group-a", app_id="bot-a", timestamp=None):
    return group_push.handle_group_command(text, app_id=app_id, app_secret="secret", group_openid=group, member_role=role,
                                          message_timestamp=timestamp if timestamp is not None else group_push.utcnow().isoformat())


def price_event():
    return create_price_change_event(offer_id=1, product_name="ChatGPT Plus", shop_name="商家",
                                    source_platform="ldxp", old_price=Decimal("100"), new_price=Decimal("80"))


def send(factory, *, snapshot=1, events=None, team=None):
    with factory() as db:
        group_push.dispatch_group_alerts([price_event()] if events is None else events, team or [], db=db,
            snapshot_id=snapshot, detected_at=datetime(2026, 11, 21, 7, tzinfo=timezone.utc), site_url="https://ai.pricememo.cn")


def test_join_is_not_opt_in_native_events_sync_and_replays_cannot_reenable(setup):
    factory, sent, *_ = setup
    native("GROUP_ADD_ROBOT")
    assert group_row(factory).subscribed is False
    send(factory)
    assert sent == []
    native("GROUP_MSG_RECEIVE", 2)
    assert group_row(factory).subscribed and group_row(factory).allow_proactive
    native("GROUP_MSG_REJECT", 3)
    native("GROUP_MSG_RECEIVE", 2)
    native("GROUP_MSG_RECEIVE", 3)
    assert not group_row(factory).subscribed
    native("GROUP_MSG_RECEIVE", 4)
    native("GROUP_DEL_ROBOT", 5)
    native("GROUP_MSG_RECEIVE", 4)
    assert not group_row(factory).is_member


def test_native_disable_wins_when_two_events_have_the_same_second(setup):
    factory, *_ = setup
    native("GROUP_MSG_RECEIVE", 2)
    native("GROUP_MSG_REJECT", 2)
    assert not group_row(factory).subscribed


def test_delayed_enable_event_cannot_reverse_a_later_manual_disable(setup):
    factory, _, _, _, clock, _ = setup
    native("GROUP_MSG_RECEIVE", 1)
    clock[0] += timedelta(seconds=10)
    command("关闭群推送")
    native("GROUP_MSG_RECEIVE", 5)
    assert not group_row(factory).subscribed
    native("GROUP_MSG_RECEIVE", 11)
    assert group_row(factory).subscribed


@pytest.mark.parametrize("role", ["member", "", "OWNER", "admin injected"])
def test_only_verified_group_owner_or_admin_can_change_subscription(setup, role):
    factory, *_ = setup
    assert "只有群主或管理员" in command(role=role)
    assert group_row(factory) is None
    command()
    assert "只有群主或管理员" in command("关闭群推送", role=role)
    assert group_row(factory).subscribed


def test_admin_opt_in_whitelist_unknown_and_native_denial_are_distinct(setup):
    factory, _, _, state, clock, _ = setup
    state[0] = None
    assert "实际发送仍由群内通知开关控制" in command(role="admin")
    assert group_row(factory).allow_proactive is None and group_row(factory).subscribed
    state[0] = {"allow_proactive_msg": False}
    clock[0] += timedelta(seconds=1)
    assert "权限未开启" in command()
    assert group_row(factory).allow_proactive is False
    state[0] = None
    clock[0] += timedelta(seconds=1)
    command()
    assert group_row(factory).allow_proactive is False
    assert "已关闭" in command("关闭群推送")
    assert not group_row(factory).subscribed


def test_one_active_digest_per_group_snapshot_and_no_cross_app_credentials(setup):
    factory, sent, *_ = setup
    command()
    command(group="group-a", app_id="bot-b")
    send(factory)
    send(factory)
    assert len(sent) == 1 and sent[0][:2] == ("bot-a", "group-a")
    assert "/alerts?view=drops" in sent[0][2]
    assert group_row(factory).last_sent_at is not None
    assert group_row(factory, app_id="bot-b").last_snapshot_id is None


@pytest.mark.parametrize("code,disabled", [(40034105, True), (40034101, True), (40054003, True), (500, False), (-1, False)])
def test_errors_stop_or_wait_for_next_snapshot_without_replaying_uncertain_sends(setup, code, disabled):
    factory, sent, errors, *_ = setup
    command()
    errors.append(code)
    send(factory)
    send(factory)
    row = group_row(factory)
    assert len(sent) == 1 and row.last_error_code == code and row.last_sent_at is None
    assert (row.allow_proactive is False) == disabled
    if code in {40034101, 40054003}:
        assert not row.is_member and not row.subscribed


def test_native_reenable_recovers_permission_denied_for_next_snapshot(setup):
    factory, sent, errors, *_ = setup
    command()
    errors.append(40034105)
    send(factory)
    native("GROUP_MSG_RECEIVE")
    with factory() as db:
        db.add(CatalogSnapshot(published_at=datetime.now(timezone.utc)))
        db.commit()
    send(factory, snapshot=2)
    assert len(sent) == 2 and group_row(factory).last_error_code is None


@pytest.mark.parametrize("code", [40034100, 429])
def test_rate_limit_stops_remaining_groups_for_that_bot(setup, code):
    factory, sent, errors, *_ = setup
    command()
    command(group="group-b")
    errors.append(code)
    send(factory)
    assert len(sent) == 1
    assert group_row(factory, group="group-b").last_snapshot_id is None


def test_no_empty_or_superseded_notifications_and_recheck_team_expiry_after_wait(setup):
    factory, sent, _, _, clock, sleeps = setup
    command()
    command(group="group-b")
    soon = TeamLowPriceOffer(1, "Team 5x", "商家", Decimal("10"), "", clock[0] + timedelta(seconds=1))
    send(factory, events=[], team=[soon])
    assert len(sent) == 1 and sleeps and "Team 车" in sent[0][2]
    with factory() as db:
        db.add(CatalogSnapshot(published_at=clock[0]))
        db.commit()
    send(factory, snapshot=1)
    assert len(sent) == 1
    send(factory, snapshot=2, events=[], team=[])
    assert len(sent) == 1


def test_global_switch_gates_group_dispatch(setup, monkeypatch):
    factory, sent, *_ = setup
    command()
    monkeypatch.setattr(dispatcher, "TelegramBotClient", lambda: type("Disabled", (), {"is_configured": False})())
    with factory() as db:
        db.add(SystemSetting(key="bot_enabled", value="false"))
        db.commit()
        dispatch_price_changes([price_event()], db_session=db, snapshot_id=1)
        assert sent == []
        db.scalar(select(SystemSetting).where(SystemSetting.key == "bot_enabled")).value = "true"
        db.commit()
        dispatch_price_changes([price_event()], db_session=db, snapshot_id=1)
    assert len(sent) == 1


def test_gateway_carries_role_and_replies_to_command_passively(setup):
    factory, *_ = setup
    replies = []
    async def run():
        service = qq_gateway.QQGatewayService()
        class ReplyBot:
            def send_group_message(self, **kwargs):
                replies.append(kwargs)
                return True
        service.bot_client = ReplyBot()
        queue = asyncio.Queue()
        service._enqueue_message(queue, "<@!123> 开启群推送", "member-a", "group-a", "msg-1", member_role="owner",
                                 message_timestamp=group_push.utcnow().isoformat())
        worker = asyncio.create_task(service._reply_worker(queue, "bot-a", "secret-a"))
        await asyncio.wait_for(queue.join(), timeout=3)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    asyncio.run(run())
    assert group_row(factory).subscribed
    assert replies[0]["msg_id"] == "msg-1" and replies[0]["group_openid"] == "group-a"


def test_group_open_api_payload_and_permission_error_are_distinguished(monkeypatch):
    requests = []
    code = [None]
    def respond(request):
        requests.append(request)
        if request.url.path.endswith("bot_state"):
            return httpx.Response(403, json={"code": 11253})
        return httpx.Response(200, json={"id": "sent"}) if code[0] is None else httpx.Response(400, json={"code": code[0]})
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    client = QQBotClient(app_id="test-bot", app_secret="not-real")
    monkeypatch.setattr(client, "_get_access_token", lambda *args: "test-token")
    assert client.get_group_state("test-group") is None
    assert client.last_group_error_code == 11253
    assert client.send_group_message("test-group", "digest")
    payload = json.loads(requests[-1].content)
    assert payload == {"content": "digest", "msg_type": 0}
    assert requests[-1].url.path == "/v2/groups/test-group/messages"
    assert requests[-1].headers["X-Union-Appid"] == "test-bot"
    assert client.send_group_message("test-group", "reply", msg_id="original")
    assert json.loads(requests[-1].content)["msg_id"] == "original"
    code[0] = 40034105
    assert not client.send_group_message("test-group", "digest")
    assert client.last_group_error_code == 40034105


def test_digest_caps_long_titles_and_deduplicates_without_losing_latest_links():
    events = [create_price_change_event(offer_id=i, product_name=f"报价{i} " + "很长标题" * 60, shop_name="店铺" * 40,
              source_platform="ldxp", old_price=Decimal("20"), new_price=Decimal("10") if i < 5 else Decimal("30")) for i in range(10)]
    now = datetime.now(timezone.utc)
    team = [TeamLowPriceOffer(i, f"Team {i} " + "很长标题" * 60, "店铺" * 40, Decimal("15"), "", now + timedelta(hours=1)) for i in range(8)]
    message = render_qq_group_digest(events + events, team + team, detected_at=now)
    assert len(message.encode("utf-8")) <= 3500
    assert "降价 5 款" in message and "涨价 5 款" in message and "Team 车 8 款" in message
    for view in ("drops", "rises", "team"):
        assert f"/alerts?view={view}" in message


def test_same_second_join_then_receive_subscribes_but_rejoin_keeps_known_denial(setup):
    factory, _, _, state, *_ = setup
    native("GROUP_ADD_ROBOT", 1)
    native("GROUP_MSG_RECEIVE", 1)
    assert group_row(factory).subscribed
    native("GROUP_DEL_ROBOT", 2)
    native("GROUP_ADD_ROBOT", 3)
    state[0] = None
    command(timestamp="2026-11-21T07:00:04Z")
    assert group_row(factory).allow_proactive is False


def test_old_queued_enable_and_missing_timestamp_cannot_override_manual_disable(setup):
    factory, *_ = setup
    command(timestamp="2026-11-21T07:00:01Z")
    command("关闭群推送", timestamp="2026-11-21T07:00:03Z")
    assert "较早" in command(timestamp="2026-11-21T07:00:02Z")
    assert "无法确认" in command(timestamp="")
    assert not group_row(factory).subscribed


def test_late_send_error_does_not_override_a_new_native_enable(setup, monkeypatch):
    factory, _, errors, _, clock, _ = setup
    command()
    original = group_push.QQBotClient.send_group_message
    def send_and_enable(self, group, message):
        clock[0] += timedelta(seconds=5)
        native("GROUP_MSG_RECEIVE", 5)
        return original(self, group, message)
    monkeypatch.setattr(group_push.QQBotClient, "send_group_message", send_and_enable)
    errors.append(40034105)
    send(factory)
    assert group_row(factory).allow_proactive is True


def test_send_denial_blocks_delayed_older_enable_event(setup):
    factory, _, errors, _, clock, _ = setup
    command()
    clock[0] += timedelta(seconds=10)
    errors.append(40034105)
    send(factory)
    native("GROUP_MSG_RECEIVE", 5)
    assert group_row(factory).allow_proactive is False
    native("GROUP_MSG_RECEIVE", 11)
    assert group_row(factory).allow_proactive is True


def test_disabling_global_switch_while_waiting_stops_remaining_groups(setup, monkeypatch):
    factory, sent, *_ = setup
    command()
    command(group="group-b")
    original = group_push.QQBotClient.send_group_message
    def send_and_disable(self, group, message):
        result = original(self, group, message)
        with factory() as db:
            db.add(SystemSetting(key="bot_enabled", value="false"))
            db.commit()
        return result
    monkeypatch.setattr(group_push.QQBotClient, "send_group_message", send_and_disable)
    send(factory)
    assert len(sent) == 1


def test_http_429_is_preserved_even_with_a_different_business_code():
    assert QQBotClient._group_error_code(httpx.Response(429, json={"code": 12345})) == 429


def test_native_permission_denial_is_not_lost_behind_a_newer_local_opt_out(setup):
    factory, sent, _, state, *_ = setup
    native("GROUP_MSG_RECEIVE", 1)
    command("关闭群推送", timestamp="2026-11-21T07:00:03Z")
    native("GROUP_MSG_REJECT", 2)
    state[0] = None
    command(timestamp="2026-11-21T07:00:04Z")
    send(factory)
    assert not sent and group_row(factory).allow_proactive is False


def test_credentials_revoked_during_pacing_stop_the_next_group(setup, monkeypatch):
    factory, sent, *_ = setup
    command()
    command(group="group-b")
    original = group_push.QQBotClient.send_group_message
    def send_and_revoke(self, group, message):
        result = original(self, group, message)
        monkeypatch.delenv("QQ_BOT_APP_SECRET")
        return result
    monkeypatch.setattr(group_push.QQBotClient, "send_group_message", send_and_revoke)
    send(factory)
    assert len(sent) == 1


def test_native_deny_in_flight_survives_local_opt_out_then_unknown_permission_query(setup, monkeypatch):
    factory, _, errors, state, clock, _ = setup
    command()
    original = group_push.QQBotClient.send_group_message
    def close_while_waiting(self, group, message):
        clock[0] += timedelta(seconds=2)
        command("关闭群推送")
        return original(self, group, message)
    monkeypatch.setattr(group_push.QQBotClient, "send_group_message", close_while_waiting)
    errors.append(40034105)
    send(factory)
    clock[0] += timedelta(seconds=1)
    state[0] = None
    command()
    assert group_row(factory).allow_proactive is False


def test_opaque_mentions_and_same_second_join_command_allow_admin_opt_in(setup):
    factory, *_ = setup
    native("GROUP_ADD_ROBOT", 1)
    assert group_push.group_command("<@!bot_abc> 关闭群推送") == "关闭群推送"
    command("<@!bot_abc> 开启群推送", timestamp="2026-11-21T07:00:01Z")
    assert group_row(factory).subscribed


def test_native_receive_after_same_second_state_query_is_authoritative(setup):
    factory, _, _, state, clock, _ = setup
    state[0] = {"allow_proactive_msg": False}
    clock[0] += timedelta(seconds=1)
    command()
    native("GROUP_MSG_RECEIVE", 1)
    assert group_row(factory).allow_proactive is True


def test_token_latency_cannot_push_expired_team_only_digest(setup, monkeypatch):
    factory, sent, _, _, clock, _ = setup
    command()
    offer = TeamLowPriceOffer(1, "Team 5x", "商家", Decimal("10"), "", clock[0] + timedelta(seconds=1))
    def prepare(self, **kwargs):
        clock[0] += timedelta(seconds=2)
        return True
    monkeypatch.setattr(group_push.QQBotClient, "prepare_send", prepare)
    send(factory, events=[], team=[offer])
    assert not sent and group_row(factory).last_snapshot_id is None


def test_gateway_resumes_before_a_group_event_that_failed_to_persist(monkeypatch):
    sent = []
    service = qq_gateway.QQGatewayService()
    service.running = True
    monkeypatch.setattr(service.bot_client, "_get_access_token", lambda *_args: "test-token")
    calls = [0]
    def persist(*args):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("temporary database outage")
        service.running = False
    monkeypatch.setattr(qq_gateway, "apply_group_event", persist)
    event = {"op": 0, "s": 2, "t": "GROUP_MSG_REJECT", "d": {"group_openid": "group", "timestamp": 1795244400}}
    class Socket:
        def __init__(self, first):
            self.messages = [{"op": 10, "d": {"heartbeat_interval": 60000}}]
            if first:
                self.messages.append({"op": 0, "s": 1, "t": "READY", "d": {"session_id": "session"}})
            self.messages.append(event)
        async def recv(self):
            return json.dumps(self.messages.pop(0))
        async def send(self, message):
            sent.append(json.loads(message))
        async def close(self):
            pass
    connections = [0]
    async def connect(*args, **kwargs):
        connections[0] += 1
        return Socket(connections[0] == 1)
    monkeypatch.setattr(qq_gateway.websockets, "connect", connect)
    asyncio.run(asyncio.wait_for(service._run_bot_gateway("bot", "secret"), timeout=5))
    assert calls[0] == 2
    assert next(payload for payload in sent if payload["op"] == 6)["d"]["seq"] == 1
