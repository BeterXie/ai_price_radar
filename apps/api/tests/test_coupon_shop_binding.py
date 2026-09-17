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
from app.models import CouponCampaign, Shop, ShopCoupon, User, UserSession
from app.security import require_admin


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
    app.dependency_overrides[require_admin] = lambda: None
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


def test_coupon_shops_list_and_import_binding(client: TestClient, test_db):
    shop1 = Shop(id=10, token="pricememo", name="彩头AI", source_url="https://wzyp.cn/shop/pricememo")
    shop2 = Shop(id=20, token="mayuan", name="码愿AI", source_url="https://pay.ldxp.cn/shop/mayuan")
    test_db.add_all([shop1, shop2])
    test_db.commit()

    # 1. Check admin_list_coupon_shops
    res = client.get("/api/v1/admin/coupons/shops")
    assert res.status_code == 200
    shops_data = res.json()
    assert len(shops_data) == 2
    assert any(s["token"] == "pricememo" and s["id"] == 10 for s in shops_data)
    assert any(s["token"] == "mayuan" and s["id"] == 20 for s in shops_data)

    # 2. Import coupons with shop_url matching shop1
    res_import1 = client.post(
        "/api/v1/admin/coupons/import",
        json={
            "name": "彩头AI 5元立减券",
            "discount_amount": 5.0,
            "min_spend": 15.0,
            "shop_url": "https://wzyp.cn/shop/pricememo",
            "codes_text": "CTAI-001\nCTAI-002",
        },
    )
    assert res_import1.status_code == 200
    assert res_import1.json()["imported_count"] == 2

    # Verify coupons in DB have shop_id = 10
    coupons1 = test_db.query(ShopCoupon).filter(ShopCoupon.code.like("CTAI%")).all()
    assert len(coupons1) == 2
    for c in coupons1:
        assert c.shop_id == 10
        assert c.shop_name == "彩头AI"
        assert c.shop_url == "https://wzyp.cn/shop/pricememo"

    # 3. Import coupons with explicit shop_id = 20
    res_import2 = client.post(
        "/api/v1/admin/coupons/import",
        json={
            "name": "码愿AI 10元券",
            "discount_amount": 10.0,
            "min_spend": 30.0,
            "shop_id": 20,
            "codes_text": "MYAI-001\nMYAI-002",
        },
    )
    assert res_import2.status_code == 200
    assert res_import2.json()["imported_count"] == 2

    coupons2 = test_db.query(ShopCoupon).filter(ShopCoupon.code.like("MYAI%")).all()
    assert len(coupons2) == 2
    for c in coupons2:
        assert c.shop_id == 20
        assert c.shop_name == "码愿AI"


def test_campaign_redemption_strictly_scoped_to_shop(client: TestClient, test_db):
    shop_a = Shop(id=10, token="pricememo", name="彩头AI", source_url="https://wzyp.cn/shop/pricememo")
    shop_b = Shop(id=20, token="mayuan", name="码愿AI", source_url="https://pay.ldxp.cn/shop/mayuan")
    test_db.add_all([shop_a, shop_b])
    test_db.commit()

    now = datetime.now(timezone.utc)
    future = now + timedelta(days=30)

    # Shop A has only 1 coupon
    coupon_a = ShopCoupon(
        name="彩头券",
        code="A-001",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("15.00"),
        shop_id=10,
        shop_name="彩头AI",
        shop_url="https://wzyp.cn/shop/pricememo",
        is_assigned=False,
        expires_at=future,
    )
    # Shop B has 5 coupons
    coupon_b = ShopCoupon(
        name="码愿券",
        code="B-001",
        discount_amount=Decimal("10.00"),
        min_spend=Decimal("30.00"),
        shop_id=20,
        shop_name="码愿AI",
        shop_url="https://pay.ldxp.cn/shop/mayuan",
        is_assigned=False,
        expires_at=future,
    )
    test_db.add_all([coupon_a, coupon_b])
    test_db.commit()

    # Create Campaign for Shop A
    res_camp_a = client.post(
        "/api/v1/admin/coupons/campaigns",
        json={
            "campaign_code": "SHOPA888",
            "title": "彩头专享口令",
            "shop_id": 10,
            "max_per_user": 1,
            "total_quota": 10,
        },
    )
    assert res_camp_a.status_code == 200
    assert res_camp_a.json()["shop_id"] == 10
    assert res_camp_a.json()["shop_name"] == "彩头AI"

    # User 1 claims Campaign A
    u1 = User(id=1, email="user1@example.com", nickname="用户1")
    u2 = User(id=2, email="user2@example.com", nickname="用户2")
    test_db.add_all([u1, u2])
    test_db.commit()

    headers1 = _login_user(test_db, u1, client)
    res_claim1 = client.post("/api/v1/user/coupons/redeem", json={"code": "SHOPA888"}, headers=headers1)
    assert res_claim1.status_code == 200
    assert res_claim1.json()["success"] is True
    claimed = res_claim1.json()["coupon"]
    assert claimed["code"] == "A-001"
    assert claimed["shop_id"] == 10
    assert claimed["shop_name"] == "彩头AI"

    # User 2 tries to claim Campaign A
    # Shop A is out of coupons! It must NOT dispense Shop B's coupon!
    headers2 = _login_user(test_db, u2, client)
    res_claim2 = client.post("/api/v1/user/coupons/redeem", json={"code": "SHOPA888"}, headers=headers2)
    assert res_claim2.status_code == 200
    assert res_claim2.json()["success"] is False
    assert "已被领完或库存不足" in res_claim2.json()["message"]

    # Verify coupon B is still unassigned
    db_b = test_db.get(ShopCoupon, coupon_b.id)
    assert db_b.is_assigned is False


def test_admin_coupons_filter_by_shop_id(client: TestClient, test_db):
    shop_a = Shop(id=10, token="pricememo", name="彩头AI", source_url="https://wzyp.cn/shop/pricememo")
    shop_b = Shop(id=20, token="mayuan", name="码愿AI", source_url="https://pay.ldxp.cn/shop/mayuan")
    test_db.add_all([shop_a, shop_b])
    test_db.commit()

    future = datetime.now(timezone.utc) + timedelta(days=30)
    c1 = ShopCoupon(name="A1", code="CA1", discount_amount=Decimal("5.00"), min_spend=Decimal("15.00"), shop_id=10, expires_at=future)
    c2 = ShopCoupon(name="B1", code="CB1", discount_amount=Decimal("5.00"), min_spend=Decimal("15.00"), shop_id=20, expires_at=future)
    test_db.add_all([c1, c2])
    test_db.commit()

    # Query all
    res_all = client.get("/api/v1/admin/coupons")
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 2

    # Query shop 10
    res_10 = client.get("/api/v1/admin/coupons?shop_id=10")
    assert res_10.status_code == 200
    assert res_10.json()["total"] == 1
    assert res_10.json()["items"][0]["code"] == "CA1"

    # Query shop 20
    res_20 = client.get("/api/v1/admin/coupons?shop_id=20")
    assert res_20.status_code == 200
    assert res_20.json()["total"] == 1
    assert res_20.json()["items"][0]["code"] == "CB1"
