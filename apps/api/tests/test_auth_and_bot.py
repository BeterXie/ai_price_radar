from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Ensure repo root is in sys.path so extensions.bots can be imported if present
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import base64
import hashlib
import os
import re

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
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
    UserProductSubscription,
    UserSession,
)
from app.services.bot_binding import check_qq_binding_session, complete_qq_binding, start_qq_binding_session
from app.services.credential_crypto import _AAD, _PREFIX, decrypt_secret, encrypt_secret
from app.services.notification_hub import create_price_change_event, dispatch_price_changes

try:
    from extensions.bots.formatter import render_qq_report, render_telegram_report
except ImportError:
    render_qq_report = None
    render_telegram_report = None


@pytest.fixture(autouse=True)
def enable_test_auth_codes(monkeypatch, bot_encryption_key):
    """This module reads login codes from its isolated database fixtures."""
    monkeypatch.setenv("DEV_PRINT_AUTH_CODES", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()



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


@pytest.fixture
def mock_auth(monkeypatch):
    """Enable the dev-only mock QQ auth (QQ_MOCK_AUTH_ENABLED) for a test."""
    monkeypatch.setenv("QQ_MOCK_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    yield True
    monkeypatch.delenv("QQ_MOCK_AUTH_ENABLED", raising=False)
    get_settings.cache_clear()


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
    assert "token" not in auth_data
    token = client.cookies.get("pm_session")
    assert token is not None
    stored_session = test_db.query(UserSession).first()
    assert stored_session is not None
    assert stored_session.token != token
    assert len(stored_session.token) == 43

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


def test_email_code_shop_scene(client: TestClient, test_db: Session) -> None:
    email = "shopuser@example.com"
    resp = client.post("/api/v1/auth/email/code", json={"email": email, "scene": "shop"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    outbox = test_db.query(NotificationOutbox).filter_by(recipient=email).first()
    assert outbox is not None
    assert "彩头软件" in outbox.subject
    assert "shop.pricememo.cn" in outbox.text_body
    assert "湖南湘江新区彩头软件开发工作室" in outbox.text_body



def test_qq_mock_oauth_callback(client: TestClient, test_db, mock_auth):
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


def test_qq_mock_auth_disabled_by_default(client: TestClient, test_db):
    """Without QQ_MOCK_AUTH_ENABLED the mock callback must fail closed."""
    resp = client.get("/api/v1/auth/qq/callback?mock=true", follow_redirects=False)
    assert resp.status_code == 303
    assert "/?auth_error=qq_disabled" in resp.headers["location"]

    scan_resp = client.get("/api/v1/auth/qq/scan-mock?session_id=whatever")
    assert scan_resp.status_code == 404


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
    assert len(bind_code) == 8
    assert check_qq_binding_session(session_id, db=test_db, user_id=999999)["status"] == "EXPIRED"

    # Check status
    st = client.get(f"/api/v1/user/notifications/qq/status?session_id={session_id}")
    assert st.status_code == 200
    assert st.json()["status"] == "WAITING"

    # Confirm binding through the trusted bot-side sender identity. The web API
    # intentionally has no endpoint that accepts a caller-supplied QQ/OpenID.
    binding = complete_qq_binding(test_db, bind_code, "qq_user_123456")
    assert binding is not None
    assert client.post(
        f"/api/v1/user/notifications/qq/confirm?bind_code={bind_code}&target_id=qq_user_123456"
    ).status_code == 404

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

    assert create_price_change_event(
        offer_id=3,
        product_name="Currency switch",
        shop_name="Shop",
        source_platform="merchant_json",
        old_price=Decimal("100.00"),
        new_price=Decimal("20.00"),
        old_currency="CNY",
        currency="USD",
    ) is None


def test_qq_qr_binding_and_bind_current_flow(client: TestClient, test_db, mock_auth):
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


@pytest.fixture
def bot_product_catalog(test_db):
    from datetime import datetime, timezone

    from app.seed import PRODUCTS

    test_db.add(CatalogSnapshot(source="test", published_at=datetime.now(timezone.utc)))
    products = {
        slug: Product(slug=slug, platform=platform, display_name=name, is_visible=True)
        for slug, platform, name, *_ in PRODUCTS
    }
    test_db.add_all(products.values())
    test_db.commit()
    return test_db, products


@pytest.mark.parametrize(
    ("command", "product_slug"),
    [
        ("gemini账号", "gemini-account"),
        ("Gemini 账号", "gemini-account"),
        ("GEMINI   账号", "gemini-account"),
        ("gemini\t账号", "gemini-account"),
        ("gemini\u3000账号", "gemini-account"),
        ("查询gemini账号", "gemini-account"),
        ("搜索 Gemini  账号", "gemini-account"),
        ("claude账号", "claude-account"),
        ("chatgpt账号", "chatgpt-account"),
        ("grok账号", "grok-account"),
        ("cursor账号", "cursor-account"),
        ("geminiadvanced", "gemini-advanced"),
        ("grokapi", "grok-api-access"),
        ("cursor pro", "cursor-pro"),
        ("cursorpro", "cursor-pro"),
        ("premium", "x-premium"),
        ("premium+", "x-premium-plus"),
        ("x premium basic", "x-premium-basic"),
        ("x premium", "x-premium"),
        ("xpremiumplus", "x-premium-plus"),
        ("claudeteam", "claude-team"),
        ("chatgpt20x", "chatgpt-pro-20x"),
        ("chatgpt pro", "chatgpt-pro-20x"),
        ("gptpro", "chatgpt-pro-20x"),
        ("chatgpt-pro", "chatgpt-pro-20x"),
        ("chatgpt 5x", "chatgpt-pro-5x"),
        ("chatgptgo", "chatgpt-go"),
        ("codexgo", "chatgpt-go"),
        ("chatgpt接码", "chatgpt-access-service"),
        ("chatgpt手机接码", "chatgpt-access-service"),
        ("free", "chatgpt-account"),
        ("codex", "chatgpt-plus"),
    ],
)
def test_bot_product_queries_accept_common_spacing(bot_product_catalog, command, product_slug):
    from extensions.bots.chat_commands import handle_chat_command

    db, products = bot_product_catalog
    reply = handle_chat_command(command, db=db)
    assert reply.startswith(f"📦【{products[product_slug].display_name}】"), reply
    assert "未找到" not in reply


@pytest.mark.parametrize("brand", ["Claude", "OpenAI", "Gemini", "Grok", "X", "Cursor"])
def test_bot_brand_recommended_queries_resolve_within_brand(bot_product_catalog, brand):
    from extensions.bots.chat_commands import BRAND_GROUPS, handle_chat_command, query_brand_lowest_prices

    db, products = bot_product_catalog
    config = BRAND_GROUPS[brand]
    brand_reply = query_brand_lowest_prices(db, brand)
    assert config["hint"] in brand_reply
    recommended_commands = re.findall(r"「([^」]+)」", config["hint"])
    assert recommended_commands
    expected_prefixes = tuple(f"📦【{product.display_name}】" for product in products.values() if product.platform == brand)
    for command in recommended_commands:
        for text in (command, "".join(command.split())):
            reply = handle_chat_command(text, db=db)
            assert reply.startswith(expected_prefixes), f"{brand}: {text}: {reply}"


def test_bot_product_name_search_preserves_word_boundaries(bot_product_catalog):
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    name = "Gemini 基础注册服务"
    db.add(Product(slug="gemini-registration-service", platform="Gemini", display_name=name, is_visible=True))
    db.commit()
    reply = handle_chat_command(f"查询 {name}", db=db)
    assert reply.startswith(f"📦【{name}】"), reply


@pytest.fixture
def bot_quote(bot_product_catalog):
    from itertools import count

    db, products = bot_product_catalog
    snapshot = db.query(CatalogSnapshot).first()
    serial = count()

    def add_quote(slug, price, *, shop=None, **attributes):
        index = next(serial)
        if shop is None:
            shop = Shop(token=f"quote-{index}", name=f"Shop {index}", source_url="https://example.com")
            db.add(shop)
            db.flush()
        raw = RawProduct(shop_id=shop.id, source_product_key=f"quote-{index}", original_name=f"Item {index}")
        db.add(raw)
        db.flush()
        values = dict(stock_status="in_stock", stock_count=5, is_comparable=True, delivery_type="finished_account", service_period="one_month")
        values.update(attributes)
        offer = Offer(
            product_id=products[slug].id, raw_product_id=raw.id, shop_id=shop.id,
            snapshot_id=snapshot.id, price=Decimal(price), source_url=f"https://example.com/{index}", **values,
        )
        db.add(offer)
        db.commit()
        return offer

    return add_quote


@pytest.mark.parametrize("stock_count", [1, None, 0])
def test_bot_prices_match_product_page_and_watchlist(bot_product_catalog, bot_quote, stock_count):
    from app.services.catalog import get_product_detail, list_product_cards
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    bot_quote("chatgpt-plus", "295", stock_count=stock_count)
    bot_quote("chatgpt-plus", "300")
    user = User(email="price-consistency@example.com")
    db.add(user)
    db.flush()
    db.add_all([
        UserBotBinding(user_id=user.id, target_id="price-user"),
        UserProductSubscription(user_id=user.id, product_slug="chatgpt-plus", target_price=Decimal("295")),
    ])
    db.commit()

    detail = get_product_detail(db, "chatgpt-plus")
    card = list_product_cards(db, product_slug="chatgpt-plus")[0]
    assert detail.lowest_price == card.lowest_price == Decimal("295")
    for command, expected in [
        ("plus", "最低在售: ¥295.00"),
        ("openai", "最低: ¥295.00"),
        ("行情", "ChatGPT Plus: 最低 ¥295.00"),
        ("关注", "最新低价: ¥295.00"),
    ]:
        reply = handle_chat_command(command, sender_id="price-user", db=db)
        assert expected in reply
        assert "库存充足" not in reply
        assert "库存>1" not in reply
        if stock_count is None:
            assert "库存数未注明" in reply
    assert "已达标" in handle_chat_command("关注", sender_id="price-user", db=db)


def test_bot_brand_reads_visible_categories_from_catalog(bot_product_catalog, bot_quote):
    from app.services.catalog import list_product_cards
    from extensions.bots.chat_commands import handle_chat_command

    db, products = bot_product_catalog
    products["chatgpt-plus"].is_visible = False
    new_product = Product(slug="new-openai-plan", platform="OpenAI", display_name="New OpenAI Plan")
    products[new_product.slug] = new_product
    db.add(new_product)
    db.commit()
    bot_quote("chatgpt-go", "34.65")
    bot_quote("chatgpt-access-service", "1.00", delivery_type="verification_service")
    bot_quote(new_product.slug, "40.00")
    reply = handle_chat_command("openai", db=db)
    cards = list_product_cards(db, platform="OpenAI")
    for card in cards:
        assert card.display_name in reply
        assert f"¥{card.lowest_price:.2f}" in reply
    assert "ChatGPT Plus" not in reply
    assert "34.65" in reply and "1.00" in reply and "New OpenAI Plan" in reply


def test_bot_ranking_merges_same_items_and_uses_site_order(bot_product_catalog, bot_quote):
    from datetime import datetime, timedelta, timezone

    from app.services.catalog import get_product_detail, get_product_recommendations
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    older = bot_quote("chatgpt-plus", "10", stock_count=100, item_fingerprint="same", observed_at=datetime.now(timezone.utc) - timedelta(hours=1))
    newer = bot_quote("chatgpt-plus", "10", shop=older.shop, stock_count=1, item_fingerprint="same")
    for index in range(1, 7):
        bot_quote("chatgpt-plus", str(10 + index), item_fingerprint=f"different-{index}")
    detail = get_product_detail(db, "chatgpt-plus")
    recommendations = get_product_recommendations(db, "chatgpt-plus")
    assert len(recommendations) == 5
    assert len({offer.item_fingerprint for offer in recommendations}) == 5
    assert recommendations[0].id == newer.id
    assert [offer.id for offer in recommendations] == [group.representative.id for group in detail.offer_groups[:5]]
    reply = handle_chat_command("plus", db=db)
    assert "同款合并" in reply
    assert "5. ¥14.00" in reply and "¥15.00" not in reply
    assert "服务期限: 1 个月" in reply


def test_bot_hidden_categories_stay_hidden_in_all_commands(bot_product_catalog, bot_quote):
    from app.services.catalog import get_product_detail, get_product_recommendations
    from extensions.bots.chat_commands import handle_chat_command

    db, products = bot_product_catalog
    offer = bot_quote("chatgpt-plus", "100")
    products["chatgpt-plus"].is_visible = False
    db.add_all([
        Product(slug="other-plus", platform="X", display_name="Other Plus Service"),
        OfferHistory(offer_id=offer.id, price=Decimal("120")),
        OfferHistory(offer_id=offer.id, price=Decimal("100")),
    ])
    user = User(email="hidden-category@example.com")
    db.add(user)
    db.flush()
    db.add_all([
        UserBotBinding(user_id=user.id, target_id="hidden-user"),
        UserProductSubscription(user_id=user.id, product_slug="chatgpt-plus"),
    ])
    db.commit()
    assert get_product_detail(db, "chatgpt-plus") is None
    assert get_product_recommendations(db, "chatgpt-plus") == []
    for command in ("plus", "chatgpt-plus", "openai", "行情", "关注", "降价"):
        reply = handle_chat_command(command, sender_id="hidden-user", db=db)
        assert "¥100.00" not in reply
        assert "/products/chatgpt-plus" not in reply
        if command in ("plus", "chatgpt-plus"):
            assert "未找到" in reply
            assert "Other Plus Service" not in reply
        else:
            assert "ChatGPT Plus" not in reply
    assert "未找到" in handle_chat_command("plus", db=db)


def test_bot_related_only_category_matches_site_expanded_scope(bot_product_catalog, bot_quote):
    from app.services.catalog import OfferFilters, get_product_detail
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    bot_quote("gemini-advanced", "20", is_comparable=False, delivery_type="shared_pool")
    bot_quote("gemini-advanced", "10", is_comparable=False, delivery_type="trial_account", stock_status="out_of_stock", stock_count=0)
    assert get_product_detail(db, "gemini-advanced").offer_group_count == 0
    assert get_product_detail(db, "gemini-advanced", filters=OfferFilters()).offer_group_count == 2
    reply = handle_chat_command("gemini advanced", db=db)
    assert "相关商品报价" in reply
    assert "¥20.00" in reply and "共享号池" in reply
    assert "已售罄" in reply
    assert "最低在售" not in reply
    assert "/products/gemini-advanced?comparable=false" in reply


def test_bot_relay_command_matches_site_cross_brand_scope(bot_product_catalog, bot_quote):
    from app.services.catalog import OfferFilters, get_catalog_group_page
    from extensions.bots.chat_commands import handle_chat_command

    db, products = bot_product_catalog
    bot_quote("openai-api-credit", "2", is_comparable=False, delivery_type="relay_api")
    bot_quote("claude-api-access", "3", currency="USD", is_comparable=False, delivery_type="relay_api")
    bot_quote("chatgpt-plus", "25", delivery_type="finished_account")
    bot_quote("gemini-api-access", "1", is_comparable=False, delivery_type="relay_api")
    products["gemini-api-access"].is_visible = False
    db.commit()
    groups, total, *_ = get_catalog_group_page(db, offset=0, limit=5, filters=OfferFilters(delivery_type="relay_api"))
    assert total == 2
    for command in ("中转", "查询中转站", "relay"):
        reply = handle_chat_command(command, db=db)
        assert "跨品牌，共 2 组" in reply
        for group in groups:
            assert group.product_name in reply
        assert "USD 3.00" in reply
        assert "Gemini API" not in reply and "ChatGPT Plus" not in reply
        assert "最低在售" not in reply


def test_bot_rejects_suspicious_price_without_claiming_insufficient_stock(bot_product_catalog, bot_quote):
    from app.services.catalog import get_product_detail
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    bot_quote("chatgpt-plus", "0.20", stock_count=5)
    assert get_product_detail(db, "chatgpt-plus").lowest_price is None
    reply = handle_chat_command("plus", db=db)
    assert "暂无通过价格校验的可比现货报价" in reply
    assert "最低在售" not in reply and "仅剩1件" not in reply


def test_bot_price_trust_matches_site_delivery_type_median(bot_product_catalog, bot_quote):
    from app.services.catalog import get_product_detail, get_product_recommendations
    from extensions.bots.chat_commands import handle_chat_command

    db, _ = bot_product_catalog
    for price in ("3", "10", "11", "12", "13"):
        bot_quote("chatgpt-plus", price)
    detail = get_product_detail(db, "chatgpt-plus")
    recommendations = get_product_recommendations(db, "chatgpt-plus")
    assert detail.lowest_price == recommendations[0].price == Decimal("10")
    assert all(offer.is_trusted_price for offer in recommendations)
    reply = handle_chat_command("plus", db=db)
    assert "最低在售: ¥10.00" in reply and "¥3.00" not in reply


def test_bot_chat_commands(client: TestClient, test_db):
    try:
        import extensions.bots.chat_commands  # noqa: F401  (availability probe)
    except ImportError:
        pytest.skip("extensions.bots not available in open-source environment")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # 0. Login: command identity is derived from the authenticated user's
    # binding; payload.sender_id is ignored by the endpoint.
    bot_email = "botchat@example.com"
    client.post("/api/v1/auth/email/code", json={"email": bot_email})
    login_code = test_db.query(AuthCode).filter_by(email=bot_email).first().code
    verify_resp = client.post("/api/v1/auth/email/verify", json={"email": bot_email, "code": login_code})
    assert verify_resp.status_code == 200

    # 1. Snapshot
    snap = CatalogSnapshot(id=1, source="test", offer_count=3, published_at=now)
    test_db.add(snap)

    # 2. Shops
    shop1 = Shop(id=1, token="shop1", name="极客小铺", source_url="https://shop1.com", is_visible=True)
    shop2 = Shop(id=2, token="shop2", name="AI特惠店", source_url="https://shop2.com", is_visible=True)
    test_db.add_all([shop1, shop2])

    # 3. Products
    p_plus = Product(id=1, slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus", is_visible=True)
    p_pro = Product(id=2, slug="claude-pro", platform="Claude", display_name="Claude Pro (5x)", is_visible=True)
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
    # Offer 1: Valid higher price offer.
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
    # Offer 2: Single-stock quotes participate in the website's lowest price.
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

    # A. The bot must agree with the website, including single-stock quotes.
    resp = client.post("/api/v1/user/notifications/bot/command", json={"text": "plus"})
    assert resp.status_code == 200
    reply = resp.json()["reply"]
    assert "ChatGPT Plus" in reply
    assert "120.00" in reply
    assert "最低在售: ¥80.00" in reply
    assert "6.80" not in reply  # unapproved offer filtered out
    assert "19.79" not in reply  # hidden offer filtered out
    assert "9.99" not in reply  # invisible shop filtered out
    assert "3. ¥135.00" in reply
    assert "极客小铺" in reply
    assert "库存 1 件" in reply

    # B. Test a category without public comparable in-stock quotes.
    resp_pro = client.post("/api/v1/user/notifications/bot/command", json={"text": "pro"})
    assert resp_pro.status_code == 200
    reply_pro = resp_pro.json()["reply"]
    assert "Claude Pro" in reply_pro
    assert "暂无通过价格校验的可比现货报价" in reply_pro

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
    assert "最低: ¥80.00" in reply_openai
    assert "6.80" not in reply_openai
    assert "19.79" not in reply_openai
    assert "9.99" not in reply_openai

    # B4. Test `20x` single product query
    resp_20x = client.post("/api/v1/user/notifications/bot/command", json={"text": "20x"})
    assert resp_20x.status_code == 200
    assert "Claude Pro 20x" in resp_20x.json()["reply"]

    # B5. Test `cursor` brand aggregation command
    resp_cursor = client.post("/api/v1/user/notifications/bot/command", json={"text": "cursor"})
    assert resp_cursor.status_code == 200
    assert "Cursor 全系列最低报价一览" in resp_cursor.json()["reply"]

    # B6. 智谱 was retired from the catalog: the bot must no longer resolve it
    # to a brand aggregation.
    resp_zhipu = client.post("/api/v1/user/notifications/bot/command", json={"text": "智谱"})
    assert resp_zhipu.status_code == 200
    assert "智谱 (GLM) 全系列最低报价一览" not in resp_zhipu.json()["reply"]

    # C. Test `行情` command
    resp_mkt = client.post("/api/v1/user/notifications/bot/command", json={"text": "行情"})
    assert resp_mkt.status_code == 200
    reply_mkt = resp_mkt.json()["reply"]
    assert "大盘行情" in reply_mkt
    assert "ChatGPT Plus: 最低 ¥80.00" in reply_mkt

    # D. Test `help` command
    resp_help = client.post("/api/v1/user/notifications/bot/command", json={"text": "help"})
    assert resp_help.status_code == 200
    assert "常用指令" in resp_help.json()["reply"]

    # E. Test User Binding & Preference commands
    chat_user = test_db.query(User).filter_by(email=bot_email).first()
    assert chat_user is not None
    binding = UserBotBinding(
        user_id=chat_user.id,
        channel="qq",
        target_id="qq_test_user_777",
        is_active=True,
        notify_price_drop=True,
        notify_price_hike=True,
    )
    test_db.add(binding)
    test_db.commit()

    # Send "我的" (no sender_id: identity comes from the logged-in user's binding)
    resp_my = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "我的"},
    )
    assert resp_my.status_code == 200
    assert "推送总状态: 🟢 开启中" in resp_my.json()["reply"]

    # Send "暂停推送"
    resp_pause = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "暂停推送"},
    )
    assert "已为您暂停全部消息推送" in resp_pause.json()["reply"]
    test_db.refresh(binding)
    assert binding.is_active is False

    # Send "恢复推送"
    resp_resume = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "恢复推送"},
    )
    assert "已为您恢复消息推送" in resp_resume.json()["reply"]
    test_db.refresh(binding)
    assert binding.is_active is True

    # Send "关闭降价"
    resp_drop_off = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "关闭降价"},
    )
    assert "已关闭【降价通知】" in resp_drop_off.json()["reply"]
    test_db.refresh(binding)
    assert binding.notify_price_drop is False

    # Send "开启降价"
    resp_drop_on = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": "开启降价"},
    )
    assert "已开启【降价通知】" in resp_drop_on.json()["reply"]
    test_db.refresh(binding)
    assert binding.notify_price_drop is True

    # F. Test In-chat /bind command: the sender identity is the logged-in
    # user's own binding target, so /bind rebinds their own session to it.
    start_res = start_qq_binding_session(test_db, chat_user.id)
    bind_code = start_res["bind_code"]
    resp_bind = client.post(
        "/api/v1/user/notifications/bot/command",
        json={"text": f"/bind {bind_code}"},
    )
    assert "绑定成功" in resp_bind.json()["reply"]
    test_db.refresh(binding)
    assert binding.is_active is True
    assert binding.target_id == "qq_test_user_777"

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


def test_qq_connector_protocol(monkeypatch):
    try:
        from extensions.bots.qq_connector import QQConnectorClient
    except ImportError:
        pytest.skip("extensions.bots not available in open-source environment")
    import secrets, base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Offline stand-in for the Tencent connector endpoints so CI never hits
    # the real network (offline runs, throttling or outages must not fail tests).
    state: dict = {}

    class _Resp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeConnectorHttp:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            if "create_bind_task" in url:
                state["key"] = json["key"]
                return _Resp({"retcode": 0, "data": {"task_id": "task-123"}})
            if "poll_bind_result" in url:
                state["polls"] = state.get("polls", 0) + 1
                if state.get("corrupt"):
                    return _Resp(
                        {
                            "retcode": 0,
                            "data": {
                                "status": 2,
                                "bot_appid": "102030405",
                                "bot_encrypt_secret": "bm90LXZhbGlkLWNpcGhlcnRleHQ=",
                                "user_openid": "openid-test-abc",
                            },
                        }
                    )
                if state["polls"] == 1:
                    return _Resp({"retcode": 0, "data": {"status": 1}})
                raw_key = base64.b64decode(state["key"])
                aes = AESGCM(raw_key)
                nonce = secrets.token_bytes(12)
                ct = aes.encrypt(nonce, b"qq_app_secret_test_987654321", None)
                encrypted = base64.b64encode(nonce + ct).decode("ascii")
                return _Resp(
                    {
                        "retcode": 0,
                        "data": {
                            "status": 2,
                            "bot_appid": "102030405",
                            "bot_encrypt_secret": encrypted,
                            "user_openid": "openid-test-abc",
                        },
                    }
                )
            raise AssertionError(f"unexpected connector url: {url}")

    monkeypatch.setattr("extensions.bots.qq_connector.httpx.Client", _FakeConnectorHttp)

    connector = QQConnectorClient()
    # 1. Test starting bind task
    res = connector.start_bind_task()
    assert res.get("task_id") == "task-123"
    assert res.get("key")
    assert "q.qq.com/qqbot/openclaw/connect.html" in res.get("qrcode_url", "")

    # 2. Test polling bind task (pending -> completed with decrypted secret)
    poll_res = connector.poll_bind_task(res["task_id"], res["key"])
    assert poll_res.get("status") == "PENDING"

    poll_done = connector.poll_bind_task(res["task_id"], res["key"])
    assert poll_done.get("status") == "COMPLETED"
    assert poll_done.get("app_id") == "102030405"
    assert poll_done.get("app_secret") == "qq_app_secret_test_987654321"
    assert poll_done.get("user_openid") == "openid-test-abc"

    # 3. A corrupted secret must surface ERROR, never COMPLETED with empty credentials
    state["corrupt"] = True
    poll_corrupt = connector.poll_bind_task(res["task_id"], res["key"])
    assert poll_corrupt.get("status") == "ERROR"
    assert "app_secret" not in poll_corrupt

    # 4. Test AES-256-GCM decryption directly
    raw_key = secrets.token_bytes(32)
    key_b64 = base64.b64encode(raw_key).decode("ascii")
    aes = AESGCM(raw_key)
    nonce = secrets.token_bytes(12)
    plaintext = b"qq_app_secret_test_987654321"
    ct_tag = aes.encrypt(nonce, plaintext, None)
    encrypted_payload = base64.b64encode(nonce + ct_tag).decode("ascii")

    decrypted = connector.decrypt_secret(encrypted_payload, key_b64)
    assert decrypted == "qq_app_secret_test_987654321"




def test_bot_secret_encryption_roundtrip():
    secret = "test-bot-secret-value"
    encrypted = encrypt_secret(secret)
    assert encrypted.startswith("enc:v1:")
    assert secret not in encrypted
    assert decrypt_secret(encrypted) == secret


def test_bot_secret_rotation_reads_previous_key_and_rekeys(monkeypatch):
    settings = get_settings()
    old_key = "old-bot-encryption-key-material-0001"
    new_key = "new-bot-encryption-key-material-0002"
    monkeypatch.setattr(settings, "bot_secret_encryption_key", old_key)
    monkeypatch.setattr(settings, "bot_secret_encryption_previous_keys", "")
    encrypted_with_old_key = encrypt_secret("rotating-secret", settings)

    monkeypatch.setattr(settings, "bot_secret_encryption_key", new_key)
    monkeypatch.setattr(settings, "bot_secret_encryption_previous_keys", old_key)
    assert decrypt_secret(encrypted_with_old_key, settings) == "rotating-secret"

    rekeyed = encrypt_secret(encrypted_with_old_key, settings)
    assert rekeyed != encrypted_with_old_key
    assert decrypt_secret(rekeyed, settings) == "rotating-secret"


def test_encrypt_secret_refuses_public_default_session_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "bot_secret_encryption_key", "")
    monkeypatch.setattr(
        settings, "session_secret_key", "pricememo-auth-secret-key-change-in-production"
    )
    with pytest.raises(RuntimeError):
        encrypt_secret("some-bot-token")


def test_decrypt_secret_still_reads_legacy_default_key_ciphertext(monkeypatch):
    """Rows encrypted before the fail-closed change must stay readable so the
    startup re-key (migrate_bot_credentials) can upgrade them."""
    legacy_material = "pricememo-auth-secret-key-change-in-production"
    settings = get_settings()
    monkeypatch.setattr(settings, "bot_secret_encryption_key", "")
    monkeypatch.setattr(settings, "session_secret_key", legacy_material)

    legacy_key = hashlib.sha256(legacy_material.encode("utf-8")).digest()
    nonce = os.urandom(12)
    ciphertext = AESGCM(legacy_key).encrypt(nonce, b"legacy-bot-token", _AAD)
    payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    legacy_value = f"{_PREFIX}{hashlib.sha256(legacy_material.encode('utf-8')).hexdigest()[:12]}:{payload}"

    assert decrypt_secret(legacy_value, settings) == "legacy-bot-token"
