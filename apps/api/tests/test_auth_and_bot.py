import sys
from decimal import Decimal
from pathlib import Path

# Ensure repo root is in sys.path so extensions.bots can be imported if present
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    AuthCode,
    CatalogSnapshot,
    NotificationOutbox,
    Offer,
    OfferHistory,
    Product,
    RawProduct,
    Shop,
    SystemSetting,
    User,
    UserBotBinding,
    UserSession,
)
from app.services.bot_binding import complete_qq_binding, start_qq_binding_session
from app.services.notification_hub import PriceChangeEvent, create_price_change_event, dispatch_price_changes

try:
    from extensions.bots.formatter import render_qq_report, render_telegram_report
except ImportError:
    render_qq_report = None
    render_telegram_report = None



@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_email_login_flow(client: TestClient, test_db):
    email = "testuser@example.com"

    # 1. Request code
    resp = client.post("/api/v1/auth/email/code", json={"email": email})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Check database outbox
    code_record = test_db.query(AuthCode).filter_by(email=email).first()
    assert code_record is not None
    assert len(code_record.code) == 6

    outbox_record = test_db.query(NotificationOutbox).filter_by(recipient=email).first()
    assert outbox_record is not None
    assert code_record.code in outbox_record.text_body

    # Immediate second request should be throttled
    resp2 = client.post("/api/v1/auth/email/code", json={"email": email})
    assert resp2.status_code == 200
    assert resp2.json()["success"] is False
    assert resp2.json()["retry_after"] > 0

    # 2. Verify with wrong code
    verify_bad = client.post("/api/v1/auth/email/verify", json={"email": email, "code": "000000"})
    assert verify_bad.status_code == 400

    # 3. Verify with correct code
    verify_good = client.post("/api/v1/auth/email/verify", json={"email": email, "code": code_record.code})
    assert verify_good.status_code == 200
    auth_data = verify_good.json()
    assert auth_data["authenticated"] is True
    assert auth_data["user"]["email"] == email
    token = auth_data["token"]
    assert token is not None

    # Check /me with cookie
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["authenticated"] is True
    assert me_resp.json()["user"]["email"] == email

    # Check /me with Bearer token header
    client.cookies.clear()
    me_header = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_header.status_code == 200
    assert me_header.json()["authenticated"] is True

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["ok"] is True

    # Should no longer be authenticated
    me_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 200
    assert me_after.json()["authenticated"] is False


def test_qq_mock_oauth_callback(client: TestClient, test_db):
    resp = client.get("/api/v1/auth/qq/callback?mock=true", follow_redirects=False)
    assert resp.status_code == 303
    assert "/account?login_success=1" in resp.headers["location"]
    session_cookie = resp.cookies.get("pm_session")
    assert session_cookie is not None

    # Check authenticated
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["user"]["has_qq_bound"] is True


def test_user_center_and_qq_bot_binding(client: TestClient, test_db):
    # Log in first
    email = "qqbind@example.com"
    client.post("/api/v1/auth/email/code", json={"email": email})
    code = test_db.query(AuthCode).filter_by(email=email).first().code
    client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})

    # Get profile
    profile = client.get("/api/v1/user/profile")
    assert profile.status_code == 200
    assert profile.json()["user"]["email"] == email
    assert profile.json()["qq_bot_binding"] is None

    # Start QQ bot binding
    start_bind = client.post("/api/v1/user/notifications/qq/start")
    assert start_bind.status_code == 200
    bind_data = start_bind.json()
    assert "bind_code" in bind_data
    session_id = bind_data["session_id"]
    bind_code = bind_data["bind_code"]

    # Check status
    st = client.get(f"/api/v1/user/notifications/qq/status?session_id={session_id}")
    assert st.status_code == 200
    assert st.json()["status"] == "WAITING"

    # Confirm binding (e.g. user sends /bind <code_or_session> from QQ)
    confirm = client.post(
        f"/api/v1/user/notifications/qq/confirm?bind_code={bind_code}&target_id=qq_user_123456"
    )
    assert confirm.status_code == 200
    assert confirm.json()["success"] is True

    # Profile now reflects bound status
    profile_after = client.get("/api/v1/user/profile")
    assert profile_after.status_code == 200
    assert profile_after.json()["qq_bot_binding"] is not None
    assert profile_after.json()["qq_bot_binding"]["target_id"] == "qq_user_123456"
    assert profile_after.json()["qq_bot_binding"]["notify_price_drop"] is True

    # Update preferences
    pref_update = client.put(
        "/api/v1/user/notifications/qq",
        json={"notify_price_hike": False},
    )
    assert pref_update.status_code == 200
    assert pref_update.json()["notify_price_hike"] is False

    # Unbind
    unbind = client.delete("/api/v1/user/notifications/qq")
    assert unbind.status_code == 200
    assert unbind.json()["success"] is True

    # Profile no longer has binding
    profile_final = client.get("/api/v1/user/profile")
    assert profile_final.json()["qq_bot_binding"] is None


def test_price_change_event_and_formatter():
    drop_evt = create_price_change_event(
        offer_id=1,
        product_name="ChatGPT Plus",
        shop_name="极速小店",
        source_platform="ldxp",
        old_price=Decimal("150.00"),
        new_price=Decimal("135.00"),
        currency="CNY",
        product_url="https://ai.pricememo.cn/products/chatgpt-plus",
    )
    assert drop_evt is not None
    assert drop_evt.is_drop is True
    assert drop_evt.diff == Decimal("-15.00")
    assert drop_evt.percent_change == -10.0

    hike_evt = create_price_change_event(
        offer_id=2,
        product_name="Claude Pro",
        shop_name="智能数码",
        source_platform="16688",
        old_price=Decimal("160.00"),
        new_price=Decimal("168.00"),
        currency="CNY",
        product_url="https://ai.pricememo.cn/products/claude-pro",
    )
    assert hike_evt is not None
    assert hike_evt.is_drop is False
    assert hike_evt.diff == Decimal("8.00")
    assert hike_evt.percent_change == 5.0

    # Test Telegram HTML Report Formatter
    if render_telegram_report is not None:
        tg_report = render_telegram_report([drop_evt, hike_evt])
        assert "ChatGPT Plus" in tg_report
        assert "降价精选" in tg_report
        assert "涨价变动" in tg_report
        assert "135.00" in tg_report

    # Test QQ Report Formatter
    if render_qq_report is not None:
        qq_report = render_qq_report([drop_evt, hike_evt])
        assert "【PriceMemo 价格变动提醒】" in qq_report
        assert "ChatGPT Plus" in qq_report
        assert "降¥15.00" in qq_report

    # Test dispatch without throwing
    dispatch_price_changes([drop_evt, hike_evt])


def test_qq_qr_binding_and_bind_current_flow(client: TestClient, test_db):
    # 1. Login user with QQ
    cb_resp = client.get("/api/v1/auth/qq/callback?mock=true", follow_redirects=False)
    assert cb_resp.status_code == 303
    session_cookie = cb_resp.cookies.get("pm_session")
    assert session_cookie is not None
    cookies = {"pm_session": session_cookie}

    user = test_db.query(User).first()
    assert user is not None
    assert user.qq_openid is not None

    # 2. Test 1-click bind current QQ
    bind_curr_resp = client.post("/api/v1/user/notifications/qq/bind-current", cookies=cookies)
    assert bind_curr_resp.status_code == 200
    assert bind_curr_resp.json()["success"] is True
    binding = test_db.query(UserBotBinding).filter_by(user_id=user.id).first()
    assert binding is not None
    assert binding.target_id == user.qq_openid

    # 3. Test starting QR binding session
    start_resp = client.post("/api/v1/user/notifications/qq/start", cookies=cookies)
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert "qrcode_url" in start_data
    session_id = start_data["session_id"]

    # 4. Check initial WAITING status
    status_resp = client.get(f"/api/v1/user/notifications/qq/status?session_id={session_id}", cookies=cookies)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "WAITING"

    # 5. Simulate mobile QQ scanning QR code
    scan_resp = client.get(f"/api/v1/auth/qq/scan-mock?session_id={session_id}")
    assert scan_resp.status_code == 200
    assert "QQ 授权扫码成功" in scan_resp.text

    # 6. Check status updated to BOUND
    status_resp2 = client.get(f"/api/v1/user/notifications/qq/status?session_id={session_id}", cookies=cookies)
    assert status_resp2.status_code == 200
    assert status_resp2.json()["status"] == "BOUND"


def test_bot_chat_commands(client: TestClient, test_db):
    try:
        import extensions.bots.chat_commands
    except ImportError:
        pytest.skip("extensions.bots not available in open-source environment")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # 1. Snapshot
    snap = CatalogSnapshot(id=1, source="test", offer_count=3, published_at=now)
    test_db.add(snap)

    # 2. Shops
    shop1 = Shop(id=1, token="shop1", name="极客小铺", source_url="https://shop1.com", is_visible=True)
    shop2 = Shop(id=2, token="shop2", name="AI特惠店", source_url="https://shop2.com", is_visible=True)
    test_db.add_all([shop1, shop2])

    # 3. Products
    p_plus = Product(id=1, slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus", is_visible=True)
    p_pro = Product(id=2, slug="claude-pro", platform="Anthropic", display_name="Claude Pro (5x)", is_visible=True)
    p_pro20x = Product(id=3, slug="claude-pro-20x", platform="Claude", display_name="Claude Pro 20x", is_visible=True)
    p_team = Product(id=4, slug="claude-team", platform="Claude", display_name="Claude Team", is_visible=True)
    test_db.add_all([p_plus, p_pro, p_pro20x, p_team])
    test_db.flush()

    # 4. Raw products
    raw1 = RawProduct(id=1, shop_id=shop1.id, source_product_key="p1", original_name="ChatGPT Plus 充值")
    raw2 = RawProduct(id=2, shop_id=shop1.id, source_product_key="p2", original_name="ChatGPT Plus 低价单件")
    raw3 = RawProduct(id=3, shop_id=shop2.id, source_product_key="p3", original_name="ChatGPT Plus 次优")
    test_db.add_all([raw1, raw2, raw3])
    test_db.flush()

    # 5. Offers
    # Offer 1: Valid lowest price offer (price=120, stock=10, is_comparable=True)
    off1 = Offer(
        id=1,
        raw_product_id=raw1.id,
        product_id=p_plus.id,
        shop_id=shop1.id,
        snapshot_id=snap.id,
        price=Decimal("120.00"),
        stock_count=10,
        stock_status="in_stock",
        is_comparable=True,
        delivery_type="subscription_recharge",
        warranty="subscription_term",
        source_url="https://shop1.com/p1",
    )
    # Offer 2: Lower price (80.00) but stock_count=1 -> MUST NOT be chosen as lowest!
    off2 = Offer(
        id=2,
        raw_product_id=raw2.id,
        product_id=p_plus.id,
        shop_id=shop1.id,
        snapshot_id=snap.id,
        price=Decimal("80.00"),
        stock_count=1,
        stock_status="in_stock",
        is_comparable=True,
        delivery_type="finished_account",
        warranty="none",
        source_url="https://shop1.com/p2",
    )
    # Offer 3: Runner up offer (price=135.00, stock=5, is_comparable=True)
    off3 = Offer(
        id=3,
        raw_product_id=raw3.id,
        product_id=p_plus.id,
        shop_id=shop2.id,
        snapshot_id=snap.id,
        price=Decimal("135.00"),
        stock_count=5,
        stock_status="in_stock",
        is_comparable=True,
        delivery_type="team_seat",
        warranty="seven_days",
        source_url="https://shop2.com/p3",
    )
    # Offer 4: Unapproved offer with extreme low price (must be ignored by bot)
    raw4 = RawProduct(id=4, shop_id=shop1.id, source_product_key="p4", original_name="ChatGPT Plus 假低价未审核")
    off4 = Offer(
        id=4,
        raw_product_id=raw4.id,
        product_id=p_plus.id,
        shop_id=shop1.id,
        snapshot_id=snap.id,
        price=Decimal("6.80"),
        stock_count=10,
        stock_status="in_stock",
        is_comparable=True,
        approved=False,  # unapproved
    )
    # Offer 5: Hidden offer with admin ban (must be ignored by bot)
    raw5 = RawProduct(id=5, shop_id=shop1.id, source_product_key="p5", original_name="ChatGPT Plus 违规封禁")
    off5 = Offer(
        id=5,
        raw_product_id=raw5.id,
        product_id=p_plus.id,
        shop_id=shop1.id,
        snapshot_id=snap.id,
        price=Decimal("19.79"),
        stock_count=16,
        stock_status="in_stock",
        is_comparable=True,
        hidden_reason="管理员限制",  # hidden
    )
    # Offer 6: Invisible shop offer (must be ignored by bot)
    shop_hidden = Shop(id=3, token="shop_hidden", name="违规隐身店", source_url="https://hidden.com", is_visible=False)
    raw6 = RawProduct(id=6, shop_id=shop_hidden.id, source_product_key="p6", original_name="ChatGPT Plus 隐藏店铺")
    off6 = Offer(
        id=6,
        raw_product_id=raw6.id,
        product_id=p_plus.id,
        shop_id=shop_hidden.id,
        snapshot_id=snap.id,
        price=Decimal("9.99"),
        stock_count=20,
        stock_status="in_stock",
        is_comparable=True,
    )
    test_db.add_all([shop_hidden, raw4, raw5, raw6, off1, off2, off3, off4, off5, off6])
    test_db.commit()

    # A. Test `plus` command (must pick 120.00, NOT 80.00, 6.80, 19.79, or 9.99)
    resp = client.post("/api/v1/user/notifications/bot/command", json={"text": "plus"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "ChatGPT Plus" in reply
    assert "120.00" in reply
    assert "¥80.00" not in reply  # 80.00 offer has stock=1, filtered out
    assert "6.80" not in reply  # unapproved offer filtered out
    assert "19.79" not in reply  # hidden offer filtered out
    assert "9.99" not in reply  # invisible shop filtered out
    assert "次优报价: ¥135.00" in reply
    assert "极客小铺" in reply
    assert "10 件" in reply

    # B. Test `pro` command (no offers with stock > 1)
    resp_pro = client.post("/api/v1/user/notifications/bot/command", json={"text": "pro"})
    assert resp_pro.status_code == 200
    reply_pro = resp_pro.json()["reply"]
    assert "Claude Pro" in reply_pro
    assert "暂无可比且库存 > 1 的现货报价" in reply_pro

    # B2. Test `claude` brand aggregation command
    resp_claude = client.post("/api/v1/user/notifications/bot/command", json={"text": "claude"})
    assert resp_claude.status_code == 200
    reply_claude = resp_claude.json()["reply"]
    assert "Claude 全系列最低报价一览" in reply_claude
    assert "Claude Pro" in reply_claude
    assert "Claude Pro 20x" in reply_claude
    assert "Claude Team" in reply_claude

    # B3. Test `openai` brand aggregation command
    resp_openai = client.post("/api/v1/user/notifications/bot/command", json={"text": "openai"})
    assert resp_openai.status_code == 200
    reply_openai = resp_openai.json()["reply"]
    assert "OpenAI / ChatGPT 全系列最低报价一览" in reply_openai
    assert "ChatGPT Plus" in reply_openai
    assert "120.00" in reply_openai
    assert "6.80" not in reply_openai
    assert "19.79" not in reply_openai
    assert "9.99" not in reply_openai

    # B4. Test `20x` single product query
    resp_20x = client.post("/api/v1/user/notifications/bot/command", json={"text": "20x"})
    assert resp_20x.status_code == 200
    assert "Claude Pro 20x" in resp_20x.json()["reply"]

    # C. Test `行情` command
    resp_mkt = client.post("/api/v1/user/notifications/bot/command", json={"text": "行情"})
    assert resp_mkt.status_code == 200
    reply_mkt = resp_mkt.json()["reply"]
    assert "大盘行情" in reply_mkt
    assert "ChatGPT Plus: 最低 ¥120.00" in reply_mkt

    # D. Test `help` command
    resp_help = client.post("/api/v1/user/notifications/bot/command", json={"text": "help"})
    assert resp_help.status_code == 200
    assert "常用指令" in resp_help.json()["reply"]

    # E. Test User Binding & Preference commands
    user = User(id=10, email="botpref@example.com", nickname="测试小哥")
    test_db.add(user)
    binding = UserBotBinding(
        user_id=user.id,
        channel="qq",
        target_id="qq_test_user_777",
        is_active=True,
        notify_price_drop=True,
        notify_price_hike=True,
    )
    test_db.add(binding)
    test_db.commit()

    # Send "我的"
    resp_my = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "我的", "sender_id": "qq_test_user_777"},
    )
    assert resp_my.status_code == 200
    assert "推送总状态: 🟢 开启中" in resp_my.json()["reply"]

    # Send "暂停推送"
    resp_pause = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "暂停推送", "sender_id": "qq_test_user_777"},
    )
    assert "已为您暂停全部消息推送" in resp_pause.json()["reply"]
    test_db.refresh(binding)
    assert binding.is_active is False

    # Send "恢复推送"
    resp_resume = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "恢复推送", "sender_id": "qq_test_user_777"},
    )
    assert "已为您恢复消息推送" in resp_resume.json()["reply"]
    test_db.refresh(binding)
    assert binding.is_active is True

    # Send "关闭降价"
    resp_drop_off = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "关闭降价", "sender_id": "qq_test_user_777"},
    )
    assert "已关闭【降价通知】" in resp_drop_off.json()["reply"]
    test_db.refresh(binding)
    assert binding.notify_price_drop is False

    # Send "开启降价"
    resp_drop_on = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "开启降价", "sender_id": "qq_test_user_777"},
    )
    assert "已开启【降价通知】" in resp_drop_on.json()["reply"]
    test_db.refresh(binding)
    assert binding.notify_price_drop is True

    # F. Test In-chat /bind command
    start_res = start_qq_binding_session(user.id)
    bind_code = start_res["bind_code"]
    resp_bind = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": f"/bind {bind_code}", "sender_id": "qq_chat_888888"},
    )
    assert "绑定成功" in resp_bind.json()["reply"]
    test_db.refresh(binding)
    assert binding.target_id == "qq_chat_888888"

    # G. Test "降价" command with price history
    h1 = OfferHistory(offer_id=off1.id, price=Decimal("140.00"), stock_count=10, observed_at=now)
    h2 = OfferHistory(offer_id=off1.id, price=Decimal("120.00"), stock_count=10, observed_at=now)
    test_db.add_all([h1, h2])
    test_db.commit()

    resp_drops = client.post("/api/v1/user/notifications/bot/command", json={"text": "降价"})
    assert resp_drops.status_code == 200
    assert "今日降价精选" in resp_drops.json()["reply"]
    assert "ChatGPT Plus" in resp_drops.json()["reply"]
    assert "140.00 ➔ ¥120.00" in resp_drops.json()["reply"]


def test_bot_disabled_behavior(client: TestClient, test_db):
    # 1. Login user
    email = "testbotdisabled@example.com"
    client.post("/api/v1/auth/email/code", json={"email": email})
    code = test_db.query(AuthCode).filter_by(email=email).first().code
    client.post("/api/v1/auth/email/verify", json={"email": email, "code": code})

    # Default: bot_enabled is True
    profile1 = client.get("/api/v1/user/profile")
    assert profile1.status_code == 200
    assert profile1.json()["bot_enabled"] is True

    # 2. Disable bot in SystemSetting (simulating admin toggle)
    setting = test_db.query(SystemSetting).filter_by(key="bot_enabled").first()
    if setting:
        setting.value = "false"
    else:
        test_db.add(SystemSetting(key="bot_enabled", value="false"))
    test_db.commit()

    # 3. Verify profile now reports bot_enabled: False
    profile2 = client.get("/api/v1/user/profile")
    assert profile2.status_code == 200
    assert profile2.json()["bot_enabled"] is False

    # 4. Attempting to start binding should be blocked with 403
    start_resp = client.post("/api/v1/user/notifications/qq/start")
    assert start_resp.status_code == 403
    assert "机器人功能已由管理员暂时关闭" in start_resp.json()["detail"]

    # 5. Attempting to bind current should be blocked with 403
    bind_curr = client.post("/api/v1/user/notifications/qq/bind-current")
    assert bind_curr.status_code == 403

    # 6. Commands should return friendly maintenance notice
    cmd_resp = client.post("/api/v1/user/notifications/bot/command", json={"text": "plus"})
    assert cmd_resp.status_code == 200
    assert "已由管理员暂时关闭" in cmd_resp.json()["reply"]

    # 7. Price change dispatch should be skipped without error
    evt = create_price_change_event(
        offer_id=10,
        product_name="ChatGPT Plus",
        shop_name="Shop",
        source_platform="ldxp",
        old_price=Decimal("100.00"),
        new_price=Decimal("90.00"),
    )
    dispatch_price_changes([evt], db_session=test_db)


def test_qq_login_endpoint_disabled_when_not_configured(client: TestClient):
    resp = client.get("/api/v1/auth/qq/login")
    assert resp.status_code == 400
    assert "暂未开放" in resp.json()["detail"]


def test_qq_connector_protocol():
    try:
        from extensions.bots.qq_connector import QQConnectorClient
    except ImportError:
        pytest.skip("extensions.bots not available in open-source environment")
    import secrets, base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    connector = QQConnectorClient()
    # 1. Test starting bind task
    res = connector.start_bind_task()
    assert res.get("task_id")
    assert res.get("key")
    assert "q.qq.com/qqbot/openclaw/connect.html" in res.get("qrcode_url", "")

    # 2. Test polling bind task
    poll_res = connector.poll_bind_task(res["task_id"], res["key"])
    assert poll_res.get("status") == "PENDING"

    # 3. Test AES-256-GCM decryption
    raw_key = secrets.token_bytes(32)
    key_b64 = base64.b64encode(raw_key).decode("ascii")
    aes = AESGCM(raw_key)
    nonce = secrets.token_bytes(12)
    plaintext = b"qq_app_secret_test_987654321"
    ct_tag = aes.encrypt(nonce, plaintext, None)
    encrypted_payload = base64.b64encode(nonce + ct_tag).decode("ascii")

    decrypted = connector.decrypt_secret(encrypted_payload, key_b64)
    assert decrypted == "qq_app_secret_test_987654321"


