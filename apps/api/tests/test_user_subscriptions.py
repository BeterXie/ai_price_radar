import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Ensure repo root is in sys.path so extensions.bots can be imported
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    CatalogSnapshot,
    NotificationOutbox,
    Offer,
    Product,
    RawProduct,
    Shop,
    User,
    UserBotBinding,
    UserProductSubscription,
    UserSession,
)
from app.services.notification_hub import create_price_change_event, dispatch_price_changes


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



def test_user_subscriptions_crud(client: TestClient, test_db):
    now = datetime.now(timezone.utc)

    # 1. Seed Product, Shop, and CatalogSnapshot
    snap = CatalogSnapshot(id=1, source="test", offer_count=1, published_at=now)
    shop = Shop(id=1, token="shop_main", name="主打卡网", source_url="https://card.shop", is_visible=True)
    prod = Product(id=1, slug="chatgpt-plus", platform="OpenAI", display_name="ChatGPT Plus", is_visible=True)
    test_db.add_all([snap, shop, prod])
    test_db.flush()

    raw = RawProduct(id=1, shop_id=shop.id, source_product_key="k1", original_name="ChatGPT Plus 现货")
    test_db.add(raw)
    test_db.flush()

    offer = Offer(
        id=1,
        raw_product_id=raw.id,
        product_id=prod.id,
        shop_id=shop.id,
        snapshot_id=snap.id,
        price=Decimal("139.00"),
        stock_count=15,
        is_comparable=True,
        currency="CNY",
    )
    test_db.add(offer)

    from datetime import timedelta

    # 2. Seed User and Session
    token = "a" * 64  # legacy plaintext session row; lookup remains compatible until expiry
    user = User(id=1, email="subscriber@test.com", nickname="关注小明", is_active=True)
    session = UserSession(token=token, user_id=user.id, expires_at=now + timedelta(days=7))
    test_db.add_all([user, session])
    test_db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Unauthenticated request to /subscriptions fails
    unauth_resp = client.get("/api/v1/user/subscriptions")
    assert unauth_resp.status_code == 401

    # 4. Authenticated request - initial empty
    list_resp = client.get("/api/v1/user/subscriptions", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 0
    assert list_resp.json()["email_bound"] is True

    # 5. Create subscription
    create_resp = client.post(
        "/api/v1/user/subscriptions",
        json={
            "product_slug": "chatgpt-plus",
            "target_price": "140.00",
            "notify_email": True,
            "notify_bot": True,
        },
        headers=headers,
    )
    assert create_resp.status_code == 200
    sub_data = create_resp.json()
    assert sub_data["product_slug"] == "chatgpt-plus"
    assert sub_data["product_name"] == "ChatGPT Plus"
    assert sub_data["current_min_price"] == "139.00"
    assert sub_data["stock_count"] == 15
    assert sub_data["target_price"] == "140.00"

    # 6. Verify GET returns the item
    list_resp2 = client.get("/api/v1/user/subscriptions", headers=headers)
    assert list_resp2.status_code == 200
    items = list_resp2.json()["items"]
    assert len(items) == 1
    assert items[0]["product_slug"] == "chatgpt-plus"

    # 7. Update subscription (e.g. adjust target price)
    update_resp = client.post(
        "/api/v1/user/subscriptions",
        json={
            "product_slug": "chatgpt-plus",
            "target_price": "130.00",
            "notify_email": True,
            "notify_bot": False,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["target_price"] == "130.00"
    assert update_resp.json()["notify_bot"] is False

    # Partial updates change only the submitted field and avoid GET+replace races.
    patch_resp = client.patch(
        "/api/v1/user/subscriptions/chatgpt-plus",
        json={"notify_email": False},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["notify_email"] is False
    assert patch_resp.json()["notify_bot"] is False
    assert patch_resp.json()["target_price"] == "130.00"

    # 8. Delete subscription
    del_resp = client.delete("/api/v1/user/subscriptions/chatgpt-plus", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 9. Verify list is empty again
    list_resp3 = client.get("/api/v1/user/subscriptions", headers=headers)
    assert list_resp3.json()["count"] == 0



def test_targeted_subscription_price_drop_dispatch(client: TestClient, test_db):
    try:
        import extensions.bots.dispatcher
    except ImportError:
        pytest.skip("extensions.bots not available in open-source environment")

    now = datetime.now(timezone.utc)

    # 1. Seed Product, Shop, User, and UserProductSubscription
    prod = Product(id=1, slug="claude-pro", platform="Anthropic", display_name="Claude Pro", is_visible=True)
    shop = Shop(id=1, token="shop_claude", name="Claude优选", source_url="https://claude.shop", is_visible=True)
    test_db.add_all([prod, shop])
    test_db.flush()

    raw = RawProduct(id=1, shop_id=shop.id, source_product_key="c1", original_name="Claude Pro 官方充值")
    test_db.add(raw)
    test_db.flush()

    user = User(id=1, email="claude_fan@test.com", nickname="克劳德", is_active=True)
    test_db.add(user)
    test_db.flush()

    sub = UserProductSubscription(
        user_id=user.id,
        product_slug="claude-pro",
        target_price=Decimal("160.00"),
        notify_email=True,
        notify_bot=True,
    )
    binding = UserBotBinding(
        user_id=user.id,
        channel="qq",
        target_id="mock_qq_target_123",
        bot_token="",
        is_active=True,
        notify_price_drop=True,
    )
    test_db.add_all([sub, binding])
    test_db.commit()

    # 2. Trigger price drop event
    evt = create_price_change_event(
        offer_id=1,
        product_name="Claude Pro",
        shop_name="Claude优选",
        source_platform="ldxp",
        old_price=Decimal("170.00"),
        new_price=Decimal("155.00"),  # Dropped below target price 160.00
        currency="CNY",
        product_url="https://claude.shop/buy",
        product_slug="claude-pro",
    )
    assert evt is not None
    assert evt.is_drop is True

    # 3. Dispatch
    dispatch_price_changes([evt], db_session=test_db)

    # 4. Check NotificationOutbox for email
    outbox_row = test_db.query(NotificationOutbox).filter_by(event_type="price_subscription_alert").first()
    assert outbox_row is not None
    assert outbox_row.recipient == "claude_fan@test.com"
    assert "Claude Pro" in outbox_row.subject
    assert "155.00" in outbox_row.subject
    assert "170.00" in outbox_row.text_body
