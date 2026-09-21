import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.database import Base
from app.models import NotificationOutbox, ShopCoupon, User, UserActionLog, UserBotBinding, UserSession
from app.routers.admin import (
    admin_broadcast_audience,
    admin_create_broadcast,
    admin_get_user_detail,
    admin_get_user_stats,
    admin_list_broadcasts,
    admin_list_users,
    admin_toggle_user_status,
)
from app.routers.user import user_heartbeat, user_track_click
from app.schemas import AdminBroadcastCreate, AdminUserStatusUpdate, UserTrackClickRequest
from app.services.auth import create_user_session, delete_user_session, settle_session_activity
from app.services.classifier import classify_product
from app.services.outbox import process_once


def test_admin_users_stats_and_list():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        # Create user 1
        u1 = User(
            email="user1@example.com",
            nickname="Test User 1",
            last_login_at=now,
            last_login_ip="1.2.3.4",
            last_active_at=now,
            total_duration_seconds=300,
            button_click_count=5,
        )
        db.add(u1)
        db.commit()
        db.refresh(u1)

        # Create user 2 (inactive / older login)
        u2 = User(
            email="user2@example.com",
            nickname="Test User 2",
            last_login_at=now - timedelta(days=10),
            last_login_ip="5.6.7.8",
            last_active_at=now - timedelta(days=10),
            total_duration_seconds=50,
            button_click_count=2,
            is_active=False,
        )
        db.add(u2)
        db.commit()
        db.refresh(u2)

        # Add a coupon for user 1
        coupon = ShopCoupon(
            name="立减券",
            code="TEST888",
            discount_amount=Decimal("5.00"),
            min_spend=Decimal("20.00"),
            is_assigned=True,
            assigned_user_id=u1.id,
            assigned_at=now,
            expires_at=now + timedelta(days=7),
            is_used=False,
        )
        db.add(coupon)

        # Add bot binding for user 1
        bot_binding = UserBotBinding(
            user_id=u1.id,
            channel="qq",
            target_id="qq_openid_12345",
            is_active=True,
            notify_price_drop=True,
        )
        db.add(bot_binding)
        db.commit()

        # 1. Test stats
        stats = admin_get_user_stats(db=db)
        assert stats.total_users == 2
        assert stats.active_today >= 1
        assert stats.online_now >= 1
        assert stats.total_clicks == 7
        assert stats.total_coupons_held == 1

        # 2. Test list all
        page_all = admin_list_users(page=1, limit=10, q="", status="all", sort_by="last_login", order="desc", db=db)
        assert page_all.total == 2
        assert len(page_all.items) == 2
        assert page_all.items[0].id == u1.id
        assert page_all.items[0].coupon_count == 1
        assert page_all.items[0].active_coupon_count == 1
        assert page_all.items[0].button_click_count == 5
        assert page_all.items[0].is_online is True
        assert page_all.items[0].has_bot_bound is True
        assert page_all.items[0].bot_target_id == "qq_openid_12345"
        assert page_all.items[0].bot_channel == "qq"
        assert page_all.items[0].bot_active is True

        # 3. Test filter by query
        page_search = admin_list_users(page=1, limit=10, q="user2", status="all", sort_by="last_login", order="desc", db=db)
        assert page_search.total == 1
        assert page_search.items[0].id == u2.id
        assert page_search.items[0].last_login_ip == "5.6.7.8"
        assert page_search.items[0].has_bot_bound is False

        # 4. Test filter by status (online vs disabled)
        page_online = admin_list_users(page=1, limit=10, q="", status="online", sort_by="last_login", order="desc", db=db)
        assert page_online.total == 1
        assert page_online.items[0].id == u1.id

        page_disabled = admin_list_users(page=1, limit=10, q="", status="disabled", sort_by="last_login", order="desc", db=db)
        assert page_disabled.total == 1
        assert page_disabled.items[0].id == u2.id

        # 5. Test toggle status
        toggle_res = admin_toggle_user_status(
            user_id=u2.id,
            payload=AdminUserStatusUpdate(is_active=True),
            db=db,
        )
        assert toggle_res["is_active"] is True
        db.refresh(u2)
        assert u2.is_active is True
        with pytest.raises(ValidationError):
            AdminUserStatusUpdate(is_active="false")

        # 6. Test user detail
        detail = admin_get_user_detail(user_id=u1.id, db=db)
        assert detail.user.id == u1.id
        assert detail.user.has_bot_bound is True
        assert len(detail.bot_bindings) == 1
        assert detail.bot_bindings[0].target_id == "qq_openid_12345"
        assert len(detail.coupons) == 1
        assert detail.coupons[0].code == "TEST888"


def test_user_heartbeat_and_click_tracking():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        user = User(
            email="hb@example.com",
            nickname="Heartbeat User",
            last_login_at=now,
            last_active_at=now - timedelta(seconds=30),
            total_duration_seconds=100,
            button_click_count=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        session = create_user_session(db, user, ip_address="192.168.1.100", user_agent="Mozilla/5.0")
        raw_session_token = getattr(session, "_raw_token")
        assert user.last_login_ip == "192.168.1.100"
        assert session.ip_address == "192.168.1.100"
        assert session.token != raw_session_token

        user.last_active_at = now - timedelta(seconds=30)
        db.commit()

        # Mock request
        mock_request = MagicMock()
        mock_request.cookies = {"pricememo_session": raw_session_token}
        mock_request.headers = {"user-agent": "Mozilla/5.0"}
        mock_request.client.host = "192.168.1.100"

        # 1. Test heartbeat: should accumulate ~30 seconds
        hb_resp = user_heartbeat(request=mock_request, current_user=user, db=db)
        assert hb_resp.status == "ok"
        assert hb_resp.online_seconds >= 120

        # 2. Test track click
        click_payload = UserTrackClickRequest(
            button_name="去购买 (商品直达)",
            button_id="offer_123",
            page="/products/chatgpt-plus",
        )
        click_resp = user_track_click(payload=click_payload, request=mock_request, current_user=user, db=db)
        assert click_resp["status"] == "ok"
        assert click_resp["recorded"] is True
        assert click_resp["click_count"] == 1

        db.refresh(user)
        assert user.button_click_count == 1

        # Check action log was recorded
        log = db.query(UserActionLog).filter_by(user_id=user.id, action_type="button_click").first()
        assert log is not None
        assert log.action_name == "去购买 (商品直达)"
        assert log.page == "/products/chatgpt-plus"

        # 3. Test logout accumulates duration
        delete_user_session(db, raw_session_token)
        db.refresh(user)
        assert user.total_duration_seconds >= 120


def test_session_activity_stale_baseline_is_not_counted_twice():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    baseline = datetime(2026, 9, 20, 1, 0, tzinfo=timezone.utc)
    with Session(engine) as db:
        user = User(email="activity@example.com", total_duration_seconds=10, last_active_at=baseline)
        db.add(user)
        db.flush()
        session = UserSession(
            token="activity-token",
            user_id=user.id,
            last_active_at=baseline,
            expires_at=baseline + timedelta(days=1),
            created_at=baseline,
        )
        db.add(session)
        db.commit()

        settled_at = baseline + timedelta(seconds=30)
        settle_session_activity(db, user, session, now=settled_at)
        db.commit()
        db.refresh(user)
        assert user.total_duration_seconds == 40

        set_committed_value(session, "last_active_at", baseline)
        settle_session_activity(db, user, session, now=settled_at)
        db.commit()
        db.refresh(user)
        assert user.total_duration_seconds == 40


def _fake_qq_bot_module(sent_targets: list[str] | None = None):
    """Build a stand-in extensions.bots.qq_bot module that always delivers."""
    module = types.ModuleType("extensions.bots.qq_bot")
    sent = sent_targets if sent_targets is not None else []

    class QQBotClient:
        def __init__(self, app_id=None, app_secret=None, **kwargs):
            self.app_id = app_id or "test-app-id"
            self.app_secret = app_secret or "test-app-secret"

        @property
        def is_configured(self) -> bool:
            return True

        def send_c2c_message(self, target_openid, text, app_id=None, app_secret=None, msg_id=None) -> bool:
            sent.append(target_openid)
            return True

    module.QQBotClient = QQBotClient
    return module


def test_admin_broadcast_notifications():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        # User 1: email only
        u1 = User(email="u1@example.com", nickname="User 1", is_active=True)
        # User 2: email and bot
        u2 = User(email="u2@example.com", nickname="User 2", is_active=True)
        # User 3: bot only (no email)
        u3 = User(email="", nickname="User 3", is_active=True)
        # User 4: inactive user with email
        u4 = User(email="u4@example.com", nickname="User 4", is_active=False)
        db.add_all([u1, u2, u3, u4])
        db.commit()

        b2 = UserBotBinding(user_id=u2.id, channel="qq", target_id="bot_target_2", is_active=True)
        b3 = UserBotBinding(user_id=u3.id, channel="qq", target_id="bot_target_3", is_active=True)
        db.add_all([b2, b3])
        db.commit()

        # 1. Test audience preview
        aud = admin_broadcast_audience(db=db)
        assert aud.total_users == 3  # active users u1, u2, u3
        assert aud.email_users == 2  # u1, u2
        assert aud.bot_users == 2    # u2, u3
        assert aud.total_reach == 3  # distinct active users reached

        # 2. Test create broadcast (both channels)
        payload = AdminBroadcastCreate(
            operation_key="broadcast-test-both-0001",
            title="全新品牌上线测试",
            content="Cursor 与 智谱 AI 比价已上线！",
            channels=["email", "bot"],
        )
        broadcast = admin_create_broadcast(payload=payload, db=db)
        assert broadcast.id is not None
        assert broadcast.title == "全新品牌上线测试"
        assert broadcast.target_user_count == 3
        assert broadcast.email_sent_count == 0
        assert broadcast.bot_sent_count == 0
        assert broadcast.status == "queued"

        # Both transports are queued in the same database transaction.
        outbox_rows = list(
            db.query(NotificationOutbox)
            .filter(NotificationOutbox.dedupe_key.like(f"broadcast:{broadcast.id}:%"))
            .all()
        )
        assert len(outbox_rows) == 4
        recipients = {r.recipient for r in outbox_rows if r.event_type == "admin_broadcast"}
        assert recipients == {"u1@example.com", "u2@example.com"}

        delivered: list[str] = []
        assert process_once(db, send=lambda row: delivered.append(row.dedupe_key), limit=10) == 4
        db.refresh(broadcast)
        assert len(delivered) == 4
        assert broadcast.email_sent_count == 2
        assert broadcast.bot_sent_count == 2
        assert broadcast.status == "sent"

        repeated = admin_create_broadcast(payload=payload, db=db)
        assert repeated.id == broadcast.id
        assert db.query(NotificationOutbox).filter(
            NotificationOutbox.dedupe_key.like(f"broadcast:{broadcast.id}:%")
        ).count() == 4

        # 3. Test list broadcasts
        history = admin_list_broadcasts(limit=10, offset=0, db=db)
        assert len(history) == 1
        assert history[0].title == "全新品牌上线测试"
        assert history[0].email_sent_count == 2


def test_admin_broadcast_counts_only_delivered_bot_messages():
    """Undeliverable bot messages must not be reported as sent."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    module = types.ModuleType("extensions.bots.qq_bot")

    class UndeliverableQQBotClient:
        def __init__(self, app_id=None, app_secret=None, **kwargs):
            pass

        @property
        def is_configured(self) -> bool:
            return False

        def send_c2c_message(self, *args, **kwargs) -> bool:
            return False

    module.QQBotClient = UndeliverableQQBotClient

    with Session(engine) as db:
        user = User(email="bot@example.com", nickname="Bot User", is_active=True)
        db.add(user)
        db.commit()
        db.add(UserBotBinding(user_id=user.id, channel="qq", target_id="unreachable_target", is_active=True))
        db.commit()

        payload = AdminBroadcastCreate(
            operation_key="broadcast-test-bot-0002",
            title="投递失败测试",
            content="内容",
            channels=["bot"],
        )
        broadcast = admin_create_broadcast(payload=payload, db=db)
        with patch.dict(sys.modules, {"extensions.bots.qq_bot": module}):
            assert process_once(db) == 0

        assert broadcast.bot_sent_count == 0
        assert broadcast.target_user_count == 1
        assert broadcast.status == "queued"


def test_cursor_and_zhipu_classifier():
    # Cursor products
    assert classify_product("Cursor Pro 官方代充 1个月").slug == "cursor-pro"
    assert classify_product("Cursor Business 商业版 团队席位").slug == "cursor-business"
    assert classify_product("Cursor 账号 独享首登成品号").slug == "cursor-account"

    # 智谱 products (including 智普 variant)
    assert classify_product("智谱清言 会员连续包月").slug == "zhipu-qingyan-vip"
    assert classify_product("智谱 GLM-4 API 额度 Key Token").slug == "zhipu-api-credit"
    assert classify_product("智谱账号 开发者账号").slug == "zhipu-account"
    assert classify_product("智普清言 会员直充").slug == "zhipu-qingyan-vip"
    assert classify_product("智普 GLM API 资源包").slug == "zhipu-api-credit"
