from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base, get_db
from app.main import app
from app.models import Report, ReportRateLimit, Shop
from app.routers import public


def make_request(client: str = "203.0.113.7", forwarded: str = "") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (client, 1234), "headers": headers})


def test_report_rate_limit_blocks_after_configured_count(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 2)

    with Session(engine) as db:
        public._enforce_report_rate_limit(make_request(), db)
        db.commit()
        public._enforce_report_rate_limit(make_request(), db)
        db.commit()

        try:
            public._enforce_report_rate_limit(make_request(), db)
        except public.HTTPException as exc:
            assert exc.status_code == 429
            assert int(exc.headers["Retry-After"]) > 0
        else:
            raise AssertionError("third request should be rate limited")

        rate = db.scalar(select(ReportRateLimit))
        assert rate is not None
        assert rate.request_count == 2


def test_forwarded_address_only_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(public.settings, "trusted_proxy_cidrs", "10.0.0.0/8")
    assert public._client_address(make_request("10.0.0.8", "198.51.100.9")) == "198.51.100.9"
    assert public._client_address(make_request("203.0.113.8", "198.51.100.9")) == "203.0.113.8"


def test_report_endpoint_returns_429(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 1)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        payload = {"kind": "correction", "message": "这是一条可核验的价格纠错信息"}
        assert client.post("/api/v1/reports", json=payload).status_code == 201
        response = client.post("/api/v1/reports", json=payload)
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_shop_request_is_validated_normalized_and_deduplicated(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 5)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        payload = {
            "shop_url": "http://PAY.LDXP.CN/shop/JBJJWNA5/?from=merchant",
            "shop_name": "测试店铺",
            "contact": "merchant@example.com",
            "note": "主营 AI 订阅商品，请审核公开报价。",
        }
        created = client.post("/api/v1/shop-requests", json=payload)
        assert created.status_code == 201
        assert created.json()["status"] == "submitted"

        duplicate = client.post(
            "/api/v1/shop-requests",
            json={**payload, "shop_url": "https://pay.ldxp.cn/shop/jbjjwna5"},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["status"] == "already_pending"

        with Session(engine) as db:
            reports = list(db.scalars(select(Report).where(Report.kind == "shop_request")))
            assert len(reports) == 1
            assert "店铺链接：https://pay.ldxp.cn/shop/JBJJWNA5" in reports[0].message
            assert reports[0].contact == "merchant@example.com"
    finally:
        app.dependency_overrides.clear()


def test_shop_request_reports_known_shop_without_creating_report(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 5)
    with Session(engine) as db:
        db.add(Shop(token="KNOWN01", name="Known", source_url="https://pay.ldxp.cn/shop/KNOWN01"))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/shop-requests",
            json={"shop_url": "https://pay.ldxp.cn/shop/known01"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "already_known"
        with Session(engine) as db:
            assert db.scalar(select(Report)) is None
    finally:
        app.dependency_overrides.clear()


def test_shop_request_rejects_non_ldxp_url(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(public.settings, "report_rate_limit_count", 5)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/shop-requests",
            json={"shop_url": "https://example.com/shop/JBJJWNA5"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
