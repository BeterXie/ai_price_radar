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


def test_user_coupons_unauthenticated(client: TestClient):
    res = client.get("/api/v1/user/coupons")
    assert res.status_code == 401

    res = client.post("/api/v1/user/coupons/redeem", json={"code": "RADAR888"})
    assert res.status_code == 401

    res = client.post("/api/v1/user/coupons/claim-drop")
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
    res = client.post("/api/v1/user/coupons/claim-drop", headers=headers)
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
    res2 = client.post("/api/v1/user/coupons/claim-drop", headers=headers)
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
    res = client.post("/api/v1/user/coupons/claim-drop", headers=headers)
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

        # 3. Batch import coupons
        import_payload = {
            "name": "满15减5元专享立减券",
            "discount_amount": 5.0,
            "min_spend": 15.0,
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


