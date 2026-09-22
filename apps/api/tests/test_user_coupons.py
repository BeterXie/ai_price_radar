import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

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
from app.models import CouponCampaign, ShopCoupon, User, UserSession
from app.routers.user import _encode_drop_claim_token


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


def _login_user(test_db, user: User, client: TestClient) -> dict[str, str]:
    import secrets
    token = secrets.token_hex(32)
    session = UserSession(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    test_db.add(session)
    test_db.commit()
    client.cookies.set("pm_session", token)
    return {"Authorization": f"Bearer {token}"}


def _drop_token() -> str:
    return _encode_drop_claim_token(issued_at=datetime.now(timezone.utc))


def test_user_coupons_unauthenticated(client: TestClient):
    res = client.get("/api/v1/user/coupons")
    assert res.status_code == 401

    res = client.post("/api/v1/user/coupons/redeem", json={"code": "RADAR888"})
    assert res.status_code == 401

    res = client.post(
        "/api/v1/user/coupons/claim-drop",
        json={"claim_token": _drop_token()},
    )
    assert res.status_code == 401


def test_user_coupons_empty_wallet(client: TestClient, test_db):
    user = User(id=1, email="test@example.com", nickname="测试员")
    test_db.add(user)
    test_db.commit()
    headers = _login_user(test_db, user, client)

    res = client.get("/api/v1/user/coupons", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 0
    assert data["items"] == []


def test_claim_lucky_drop_success_and_rate_limit(client: TestClient, test_db):
    user = User(id=1, email="test@example.com", nickname="测试员")
    test_db.add(user)

    future = datetime.now(timezone.utc) + timedelta(days=30)
    coupon1 = ShopCoupon(
        coupon_batch_id=11529,
        name="彩头AI专享立减券 (满15减5)",
        code="3602984211",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    coupon2 = ShopCoupon(
        coupon_batch_id=11529,
        name="彩头AI专享立减券 (满15减5)",
        code="4432078218",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    test_db.add_all([coupon1, coupon2])
    test_db.commit()

    headers = _login_user(test_db, user, client)

    # First claim: Success
    res = client.post(
        "/api/v1/user/coupons/claim-drop",
        json={"claim_token": _drop_token()},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["coupon"]["code"] == "3602984211"
    assert float(data["coupon"]["discount_amount"]) == 5.0
    assert float(data["coupon"]["min_spend"]) == 15.0

    # Wallet check
    res = client.get("/api/v1/user/coupons", headers=headers)
    assert res.status_code == 200
    wallet = res.json()
    assert wallet["count"] == 1
    assert wallet["items"][0]["code"] == "3602984211"

    # Second claim within 24 hours: Cooldown rejected
    res2 = client.post(
        "/api/v1/user/coupons/claim-drop",
        json={"claim_token": _drop_token()},
        headers=headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is False
    assert "24 小时" in data2["message"]
    assert data2["coupon"]["code"] == "3602984211"


def test_claim_lucky_drop_pool_exhausted(client: TestClient, test_db):
    user = User(id=1, email="test@example.com", nickname="测试员")
    test_db.add(user)
    test_db.commit()
    headers = _login_user(test_db, user, client)

    # Empty coupon pool
    res = client.post(
        "/api/v1/user/coupons/claim-drop",
        json={"claim_token": _drop_token()},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "抢光" in data["message"]


def test_redeem_campaign_code(client: TestClient, test_db):
    user = User(id=1, email="test@example.com", nickname="测试员")
    test_db.add(user)

    future = datetime.now(timezone.utc) + timedelta(days=30)
    campaign = CouponCampaign(
        campaign_code="RADAR888",
        title="雷达站专属回馈",
        coupon_batch_id=11529,
        max_per_user=1,
        total_quota=50,
        claimed_count=0,
        is_active=True,
        expires_at=future,
    )
    coupon = ShopCoupon(
        coupon_batch_id=11529,
        name="满15减5元口令券",
        code="2001954499",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    test_db.add_all([campaign, coupon])
    test_db.commit()

    headers = _login_user(test_db, user, client)

    # Redeem with lowercase / uppercase campaign code
    res = client.post("/api/v1/user/coupons/redeem", json={"code": "radar888"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["coupon"]["code"] == "2001954499"

    # Try redeeming again: limit 1 per user
    res2 = client.post("/api/v1/user/coupons/redeem", json={"code": "RADAR888"}, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is False
    assert "限领 1 张" in data2["message"]


def test_redeem_direct_coupon_code(client: TestClient, test_db):
    user1 = User(id=1, email="user1@example.com", nickname="用户1")
    user2 = User(id=2, email="user2@example.com", nickname="用户2")
    test_db.add_all([user1, user2])

    future = datetime.now(timezone.utc) + timedelta(days=30)
    coupon = ShopCoupon(
        coupon_batch_id=11529,
        name="满15减5元专享券",
        code="6669300217",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    test_db.add(coupon)
    test_db.commit()

    headers1 = _login_user(test_db, user1, client)

    # User 1 claims via direct code
    res = client.post("/api/v1/user/coupons/redeem", json={"code": "6669300217"}, headers=headers1)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["coupon"]["code"] == "6669300217"

    # User 1 repeats: already in wallet
    res_repeat = client.post("/api/v1/user/coupons/redeem", json={"code": "6669300217"}, headers=headers1)
    assert res_repeat.status_code == 200
    assert res_repeat.json()["success"] is True
    assert "已在您的卡包中" in res_repeat.json()["message"]

    # User 2 tries to claim same code
    headers2 = _login_user(test_db, user2, client)
    res_other = client.post("/api/v1/user/coupons/redeem", json={"code": "6669300217"}, headers=headers2)
    assert res_other.status_code == 200
    assert res_other.json()["success"] is False
    assert "已被其他用户兑换" in res_other.json()["message"]


def test_direct_coupon_redemption_does_not_consume_drop_cooldown(client: TestClient, test_db):
    user = User(id=1, email="direct-then-drop@example.com", nickname="测试员")
    future = datetime.now(timezone.utc) + timedelta(days=30)
    direct_coupon = ShopCoupon(
        name="直接兑换券",
        code="DIRECT-ONLY-1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        expires_at=future,
    )
    drop_coupon = ShopCoupon(
        name="掉落券",
        code="DROP-ONLY-1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        expires_at=future,
    )
    test_db.add_all([user, direct_coupon, drop_coupon])
    test_db.commit()
    headers = _login_user(test_db, user, client)

    redeemed = client.post(
        "/api/v1/user/coupons/redeem",
        json={"code": direct_coupon.code},
        headers=headers,
    )
    assert redeemed.json()["success"] is True

    claimed = client.post(
        "/api/v1/user/coupons/claim-drop",
        json={"claim_token": _drop_token()},
        headers=headers,
    )
    assert claimed.json()["success"] is True
    assert claimed.json()["coupon"]["code"] == drop_coupon.code


def test_coupon_drop_status_and_dynamic_probability(client: TestClient, test_db):
    from app.models import SystemSetting
    now = datetime.now(timezone.utc)

    # 1. Initially empty stock
    res = client.get("/api/v1/user/coupons/drop-status")
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert data["has_stock"] is False
    assert data["remaining_stock"] == 0
    assert data["probability"] == 0

    # 2. Add 2 coupons (scarcity mode < 5)
    c1 = ShopCoupon(name="测试券1", code="code1", discount_amount=Decimal("5.00"), min_spend=Decimal("15.00"), expires_at=now + timedelta(days=5))
    c2 = ShopCoupon(name="测试券2", code="code2", discount_amount=Decimal("5.00"), min_spend=Decimal("15.00"), expires_at=now + timedelta(days=5))
    test_db.add_all([c1, c2])
    test_db.commit()

    res2 = client.get("/api/v1/user/coupons/drop-status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["has_stock"] is True
    assert data2["remaining_stock"] == 2
    # Dynamic scaling throttles probability down to <= 5%
    assert data2["probability"] <= 5

    # 3. Disable drop feature via setting
    test_db.add(SystemSetting(key="coupon_drop_enabled", value="false"))
    test_db.commit()

    res3 = client.get("/api/v1/user/coupons/drop-status")
    assert res3.status_code == 200
    assert res3.json()["enabled"] is False


def test_admin_coupon_management(client: TestClient, test_db):
    from app.security import require_admin
    app.dependency_overrides[require_admin] = lambda: None
    try:
        # 1. Query stats
        res = client.get("/api/v1/admin/coupons/stats")
        assert res.status_code == 200
        stats = res.json()
        assert "total_coupons" in stats
        assert "drop_probability" in stats

        # 2. Update settings
        res_patch = client.patch(
            "/api/v1/admin/coupons/settings",
            json={"drop_probability": 35, "drop_enabled": True, "dynamic_drop": False},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["drop_probability"] == 35
        assert res_patch.json()["dynamic_drop"] is False

        # 3. Batch import coupons. Shop binding is mandatory so coupons
        # cannot silently fall into a site-wide/default storefront pool.
        import_payload = {
            "name": "满15减5元专享立减券",
            "discount_amount": 5.0,
            "min_spend": 15.0,
            "shop_name": "测试店铺",
            "shop_url": "https://example.com/test-shop",
            "codes_text": "IMPORT1001\nIMPORT1002\nIMPORT1003,IMPORT1001",  # Contains duplicate
        }
        res_import = client.post("/api/v1/admin/coupons/import", json=import_payload)
        assert res_import.status_code == 200
        import_data = res_import.json()
        assert import_data["success"] is True
        assert import_data["imported_count"] == 3
        assert import_data["skipped_count"] == 1

        # 4. List coupons
        res_list = client.get("/api/v1/admin/coupons?status=unassigned")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] >= 3
        first_id = list_data["items"][0]["id"]

        # 5. Delete coupon
        res_del = client.delete(f"/api/v1/admin/coupons/{first_id}")
        assert res_del.status_code == 200
        assert res_del.json()["ok"] is True

        # 6. Create campaign & list campaigns
        camp_payload = {
            "campaign_code": "RADAR999",
            "title": "测试活动口令",
            "shop_url": "https://wzyp.cn/shop/pricememo",
            "max_per_user": 1,
            "total_quota": 50,
        }
        res_camp = client.post("/api/v1/admin/coupons/campaigns", json=camp_payload)
        assert res_camp.status_code == 200
        camp_id = res_camp.json()["id"]

        res_camps = client.get("/api/v1/admin/coupons/campaigns")
        assert res_camps.status_code == 200
        assert any(c["campaign_code"] == "RADAR999" for c in res_camps.json())

        # Delete campaign
        res_del_camp = client.delete(f"/api/v1/admin/coupons/campaigns/{camp_id}")
        assert res_del_camp.status_code == 200
        assert res_del_camp.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_redeem_campaign_fallback_and_independent_campaign_quotas(client: TestClient, test_db):
    user = User(id=1, email="user@example.com", nickname="测试员")
    test_db.add(user)

    future = datetime.now(timezone.utc) + timedelta(days=30)
    # Campaign with coupon_batch_id = 1, but only batch 0 coupons exist in DB
    campaign1 = CouponCampaign(
        id=1,
        campaign_code="PRIICEMEMO666",
        title="测试活动1",
        coupon_batch_id=1,
        max_per_user=1,
        total_quota=50,
        claimed_count=0,
        is_active=True,
        expires_at=future,
    )
    campaign2 = CouponCampaign(
        id=2,
        campaign_code="COMMUNITY888",
        title="测试活动2",
        coupon_batch_id=0,
        max_per_user=1,
        total_quota=50,
        claimed_count=0,
        is_active=True,
        expires_at=future,
    )
    # Two general coupons in batch 0
    coupon1 = ShopCoupon(
        id=101,
        coupon_batch_id=0,
        name="通用立减券1",
        code="GEN_CODE_1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    coupon2 = ShopCoupon(
        id=102,
        coupon_batch_id=0,
        name="通用立减券2",
        code="GEN_CODE_2",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    test_db.add_all([campaign1, campaign2, coupon1, coupon2])
    test_db.commit()

    headers = _login_user(test_db, user, client)

    # 1. Redeem campaign 1 (batch_id 1 falls back to batch 0)
    res1 = client.post("/api/v1/user/coupons/redeem", json={"code": "PRIICEMEMO666"}, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["success"] is True
    assert res1.json()["coupon"]["code"] == "GEN_CODE_1"
    assert res1.json()["coupon"]["campaign_id"] == 1

    # 2. Campaign 1 cannot be redeemed again by same user
    res1_again = client.post("/api/v1/user/coupons/redeem", json={"code": "PRIICEMEMO666"}, headers=headers)
    assert res1_again.status_code == 200
    assert res1_again.json()["success"] is False
    assert "限领 1 张" in res1_again.json()["message"]

    # 3. User CAN still redeem Campaign 2 independently!
    res2 = client.post("/api/v1/user/coupons/redeem", json={"code": "COMMUNITY888"}, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["success"] is True
    assert res2.json()["coupon"]["code"] == "GEN_CODE_2"
    assert res2.json()["coupon"]["campaign_id"] == 2


def test_record_coupon_drop_trigger_and_stats(client: TestClient, test_db):
    from app.models import UserActionLog
    from app.routers.admin import _get_coupon_stats

    # 1. Anonymous visitor triggers drop
    res_anon = client.post(
        "/api/v1/user/coupons/record-drop-trigger",
        json={"page": "/products/claude-3-5-sonnet", "extra_data": {"platform": "web"}},
    )
    assert res_anon.status_code == 200
    assert res_anon.json()["success"] is True

    # 2. Logged-in user triggers drop
    user = User(id=99, email="coupon_tester@example.com", nickname="彩蛋测试员")
    test_db.add(user)
    test_db.commit()
    headers = _login_user(test_db, user, client)

    res_user = client.post(
        "/api/v1/user/coupons/record-drop-trigger",
        json={"page": "/compare/chatgpt-vs-claude"},
        headers=headers,
    )
    assert res_user.status_code == 200
    assert res_user.json()["success"] is True

    # 3. Verify UserActionLogs
    logs = test_db.query(UserActionLog).filter_by(action_type="coupon_drop_trigger").all()
    assert len(logs) == 2
    assert any(l.user_id is None and l.page == "/products/claude-3-5-sonnet" for l in logs)
    assert any(l.user_id == 99 and l.page == "/compare/chatgpt-vs-claude" for l in logs)

    # 4. Verify stats reflects drop_trigger_count == 2
    stats = _get_coupon_stats(test_db)
    assert stats.drop_trigger_count == 2


def test_expired_unassigned_coupons_do_not_trigger_drop(client: TestClient, test_db):
    from app.routers.admin import _get_coupon_stats
    now = datetime.now(timezone.utc)

    # Only expired unassigned coupons in db
    expired_coupon = ShopCoupon(
        name="已过期测试券",
        code="EXPIRED_CODE_1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now - timedelta(hours=2),
    )
    test_db.add(expired_coupon)
    test_db.commit()

    # 1. Drop status reports 0 stock, no stock, 0 probability
    status_res = client.get("/api/v1/user/coupons/drop-status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["has_stock"] is False
    assert status_data["remaining_stock"] == 0
    assert status_data["probability"] == 0

    # 2. Triggering drop returns ineligible and no claim token
    trigger_res = client.post(
        "/api/v1/user/coupons/record-drop-trigger",
        json={"page": "/compare/chatgpt-vs-claude"},
    )
    assert trigger_res.status_code == 200
    trigger_data = trigger_res.json()
    assert trigger_data["eligible"] is False
    assert trigger_data["claim_token"] == ""

    # 3. Admin stats accurately shows droppable inventory == 0 and expired unassigned == 1
    stats = _get_coupon_stats(test_db)
    assert stats.unassigned_coupons == 0
    assert stats.expired_unassigned_coupons == 1


def test_admin_coupons_filter_and_cleanup_expired(client: TestClient, test_db):
    from app.routers.admin import admin_cleanup_expired_coupons, admin_list_coupons
    now = datetime.now(timezone.utc)

    valid_c = ShopCoupon(
        name="有效券",
        code="VALID_1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now + timedelta(days=5),
    )
    expired_c1 = ShopCoupon(
        name="过期券1",
        code="EXP_1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now - timedelta(days=1),
    )
    expired_c2 = ShopCoupon(
        name="过期券2",
        code="EXP_2",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now - timedelta(days=2),
    )
    assigned_c = ShopCoupon(
        name="已领入卡包券",
        code="ASSIGNED_1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=True,
        is_used=False,
        expires_at=now - timedelta(days=1),  # user's expired wallet coupon
    )
    test_db.add_all([valid_c, expired_c1, expired_c2, assigned_c])
    test_db.commit()

    # Query unassigned: strictly only the valid unexpired coupon
    unassigned_page = admin_list_coupons(status="unassigned", db=test_db)
    assert unassigned_page.total == 1
    assert unassigned_page.items[0].code == "VALID_1"

    # Query expired: strictly the 2 expired unassigned coupons
    expired_page = admin_list_coupons(status="expired", db=test_db)
    assert expired_page.total == 2
    codes = {item.code for item in expired_page.items}
    assert codes == {"EXP_1", "EXP_2"}

    # Cleanup expired: batch removes the 2 expired unassigned coupons
    res = admin_cleanup_expired_coupons(db=test_db)
    assert res.deleted_count == 2

    # Remaining in DB: valid coupon + user's assigned coupon (protected!)
    remaining = test_db.query(ShopCoupon).all()
    remaining_codes = {c.code for c in remaining}
    assert remaining_codes == {"VALID_1", "ASSIGNED_1"}


def test_privacy_cleanup_purges_expired_unassigned_coupons(test_db):
    from app.services.privacy import cleanup_privacy_data
    now = datetime.now(timezone.utc)

    valid_c = ShopCoupon(
        name="有效券",
        code="PRIVACY_VALID",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now + timedelta(days=2),
    )
    expired_c = ShopCoupon(
        name="过期券",
        code="PRIVACY_EXP",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=False,
        is_used=False,
        expires_at=now - timedelta(days=1),
    )
    assigned_c = ShopCoupon(
        name="用户券",
        code="PRIVACY_ASSIGNED",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        is_assigned=True,
        is_used=False,
        expires_at=now - timedelta(days=1),
    )
    test_db.add_all([valid_c, expired_c, assigned_c])
    test_db.commit()

    stats = cleanup_privacy_data(test_db)
    assert stats["expired_unassigned_coupons"] == 1

    remaining = test_db.query(ShopCoupon).all()
    remaining_codes = {c.code for c in remaining}
    assert remaining_codes == {"PRIVACY_VALID", "PRIVACY_ASSIGNED"}
