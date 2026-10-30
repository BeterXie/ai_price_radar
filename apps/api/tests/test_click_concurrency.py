"""Exercise the real click routes with independent request sessions.

SQLite uses a file and WAL, not a shared StaticPool/Session. Delays below pause
before a write; PostgreSQL row-lock integration is covered separately.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import threading
import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import Base, get_db
from app.models import CatalogSnapshot, Offer, OfferClick, Product, RawProduct, Shop, User, UserActionLog, UserSession
from app.routers import public
from app.security import get_current_user
from app.services.auth import _session_token_digest
from app.services.click_locks import ClickLocks, click_locks


@dataclass
class ClickEnvironment:
    app: FastAPI
    sessions: sessionmaker
    offer_ids: tuple[int, int]
    shop_tokens: tuple[str, str]
    user_id: int
    raw_token: str
    created_sessions: list[Session]

    def client(self, **kwargs):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, client=("127.0.0.1", 12345), **kwargs),
            base_url="http://testserver",
        )


@pytest.fixture
def click_engine(request):
    database_url = os.environ.get("CLICK_TEST_DATABASE_URL", "")
    if database_url:
        if make_url(database_url).get_backend_name() != "postgresql":
            pytest.fail("CLICK_TEST_DATABASE_URL must select the isolated PostgreSQL test server")
        schema = "click_tests_" + uuid.uuid4().hex
        admin_engine = create_engine(database_url)
        with admin_engine.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = create_engine(
            database_url,
            connect_args={"options": f"-csearch_path={schema}"},
            pool_size=8,
            max_overflow=8,
        )
        try:
            yield engine
        finally:
            engine.dispose()
            try:
                with admin_engine.begin() as conn:
                    # Only the UUID schema created by this fixture is removed.
                    conn.execute(DropSchema(schema, cascade=True))
            finally:
                admin_engine.dispose()
    else:
        tmp_path = request.getfixturevalue("tmp_path")
        engine = create_engine(
            f"sqlite:///{tmp_path / 'clicks.db'}",
            connect_args={"check_same_thread": False, "timeout": 10},
            pool_size=8,
            max_overflow=8,
        )
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def click_env(click_engine, monkeypatch):
    engine = click_engine
    Base.metadata.create_all(engine)
    # expire_on_commit=True deliberately catches accidental post-commit ORM
    # reads even though production currently disables expiration.
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)
    now = datetime.now(timezone.utc)
    raw_token = "a" * 64
    with sessions() as db:
        snapshot = CatalogSnapshot(source="click-concurrency", offer_count=2, published_at=now)
        product = Product(slug="chatgpt-plus", platform="openai", display_name="ChatGPT Plus", is_visible=True)
        user = User(email="click-test@example.test", is_active=True, last_active_at=now - timedelta(seconds=20))
        db.add_all([snapshot, product, user])
        db.flush()
        user_id = user.id
        db.add(UserSession(
            token=_session_token_digest(raw_token), user_id=user.id,
            expires_at=now + timedelta(days=1), created_at=now - timedelta(seconds=20),
            last_active_at=now - timedelta(seconds=20),
        ))
        offer_ids, shop_tokens = [], []
        for index in range(2):
            shop = Shop(token=f"click-shop-{index}", name=f"Shop {index}", source_url=f"https://shop{index}.example.test", platform="ldxp", status="normal", is_visible=True)
            db.add(shop)
            db.flush()
            raw = RawProduct(shop_id=shop.id, source_product_key=f"product-{index}", original_name="ChatGPT Plus", source_url=f"https://shop{index}.example.test/item")
            db.add(raw)
            db.flush()
            offer = Offer(
                raw_product_id=raw.id, product_id=product.id, shop_id=shop.id,
                snapshot_id=snapshot.id, price=Decimal("100"), currency="CNY",
                stock_status="in_stock", stock_count=5, active=True, approved=True,
                is_comparable=True, click_count=0, observed_at=now,
            )
            db.add(offer)
            db.flush()
            offer_ids.append(offer.id)
            shop_tokens.append(shop.token)
        db.commit()
    test_app = FastAPI()
    test_app.include_router(public.router)
    created_sessions = []

    def override_db(request: Request):
        with sessions() as db:
            db.info["request_id"] = request.headers.get("X-Test-Request", "")
            created_sessions.append(db)
            yield db

    test_app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(public.settings, "trusted_proxy_cidrs", "127.0.0.0/8")
    env = ClickEnvironment(test_app, sessions, tuple(offer_ids), tuple(shop_tokens), user_id, raw_token, created_sessions)
    try:
        yield env
    finally:
        test_app.dependency_overrides.clear()
        assert not click_locks._queues


async def _wait_until(predicate):
    async def poll():
        while not predicate():
            await asyncio.sleep(0)
    await asyncio.wait_for(poll(), timeout=3)


def _path(env, kind, index=0):
    return f"/api/v1/offers/{env.offer_ids[index]}/click" if kind == "offer" else f"/api/v1/shops/{env.shop_tokens[index]}/click"


def _key(env, kind, ip="127.0.0.1"):
    namespace = f"{kind}-click"
    target = str(env.offer_ids[0]) if kind == "offer" else env.shop_tokens[0]
    return namespace, target, public._click_ip_hash(namespace, ip)


def _is_offer_update(state):
    mapper = getattr(state, "bind_mapper", None)
    return bool(state.is_update and mapper is not None and mapper.local_table.name == "offers")


@pytest.mark.parametrize("kind", ["offer", "shop"])
def test_concurrent_same_key_records_exactly_once(click_env, kind):
    async def run():
        async with click_env.client() as client:
            return await asyncio.gather(*(client.post(_path(click_env, kind)) for _ in range(16)))
    responses = asyncio.run(run())
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()["recorded"] for response in responses) == 1
    assert len({id(db) for db in click_env.created_sessions}) == 16
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 1
        assert db.scalar(select(func.count(UserActionLog.id))) == 1
        assert db.get(Offer, click_env.offer_ids[0]).click_count == (1 if kind == "offer" else 0)


def test_many_same_key_waiters_do_not_starve_other_keys(click_env):
    key = _key(click_env, "offer")
    async def run():
        async with click_env.client() as client:
            async with click_locks.hold(key):
                waiters = [asyncio.create_task(client.post(_path(click_env, "offer"))) for _ in range(48)]
                await _wait_until(lambda: len(click_locks._queues[key]) == 49)
                assert not click_env.created_sessions
                unrelated = await asyncio.wait_for(client.post(_path(click_env, "shop", 1)), 3)
                assert unrelated.status_code == 200 and unrelated.json()["recorded"]
                assert len(click_env.created_sessions) == 1
            responses = await asyncio.wait_for(asyncio.gather(*waiters), 5)
            assert all(response.status_code == 200 for response in responses)
            assert sum(response.json()["recorded"] for response in responses) == 1
    asyncio.run(run())
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 2


def test_concurrent_different_ips_return_each_atomic_increment(click_env):
    async def run():
        async with click_env.client() as client:
            return await asyncio.gather(*(
                client.post(_path(click_env, "offer"), headers={"X-Forwarded-For": f"198.51.100.{index + 1}"})
                for index in range(12)
            ))
    responses = asyncio.run(run())
    assert all(response.status_code == 200 and response.json()["recorded"] for response in responses)
    assert sorted(response.json()["click_count"] for response in responses) == list(range(1, 13))
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 12
        assert db.scalar(select(func.count(UserActionLog.id))) == 12
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 12


def test_same_key_is_shared_between_request_event_loops(click_env):
    barrier = threading.Barrier(6)

    def request():
        barrier.wait(timeout=5)
        async def run():
            async with click_env.client() as client:
                return await client.post(_path(click_env, "offer"))
        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: request(), range(6)))
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()["recorded"] for response in responses) == 1
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 1
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 1


def test_unrelated_offer_shop_and_ip_continue_during_slow_update(click_env):
    entered, release = threading.Event(), threading.Event()

    def delay_update(state):
        if state.session.info.get("request_id") == "slow" and _is_offer_update(state):
            entered.set()
            assert release.wait(timeout=5), "slow request watchdog expired"

    event.listen(click_env.sessions.class_, "do_orm_execute", delay_update)
    async def run():
        async with click_env.client() as client:
            slow = asyncio.create_task(client.post(_path(click_env, "offer"), headers={"X-Test-Request": "slow"}))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                other_offer = await asyncio.wait_for(client.post(_path(click_env, "offer", 1)), 3)
                shop = await asyncio.wait_for(client.post(_path(click_env, "shop")), 3)
                other_ip = await asyncio.wait_for(client.post(_path(click_env, "offer"), headers={"X-Forwarded-For": "198.51.100.10"}), 3)
                assert not slow.done()
                assert all(r.status_code == 200 and r.json()["recorded"] for r in (other_offer, shop, other_ip))
                assert other_ip.json()["click_count"] == 1
            finally:
                release.set()
                result = await slow
            assert result.status_code == 200 and result.json()["click_count"] == 2
    try:
        asyncio.run(run())
    finally:
        event.remove(click_env.sessions.class_, "do_orm_execute", delay_update)
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 4
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 2


def test_postgres_row_wait_does_not_block_unrelated_offer_or_shop(click_env):
    engine = click_env.sessions.kw["bind"]
    if engine.dialect.name != "postgresql":
        pytest.skip("requires CLICK_TEST_DATABASE_URL for PostgreSQL row locks")
    blocker = click_env.sessions()
    blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
    blocker.execute(
        update(Offer).where(Offer.id == click_env.offer_ids[0]).values(observed_at=Offer.observed_at)
    )

    def has_blocked_click():
        with engine.connect() as conn:
            return bool(conn.scalar(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE :blocker = ANY(pg_blocking_pids(pid))"
            ), {"blocker": blocker_pid}))

    async def run():
        async with click_env.client() as client:
            slow = asyncio.create_task(client.post(_path(click_env, "offer")))
            try:
                async def wait_for_row_lock():
                    while not await asyncio.to_thread(has_blocked_click):
                        await asyncio.sleep(0)
                await asyncio.wait_for(wait_for_row_lock(), 3)
                other_offer = await asyncio.wait_for(client.post(_path(click_env, "offer", 1)), 3)
                shop = await asyncio.wait_for(client.post(_path(click_env, "shop")), 3)
                assert not slow.done()
                assert all(r.status_code == 200 and r.json()["recorded"] for r in (other_offer, shop))
            finally:
                blocker.rollback()
                result = await asyncio.wait_for(slow, 3)
            assert result.status_code == 200 and result.json()["click_count"] == 1

    try:
        asyncio.run(run())
    finally:
        blocker.close()
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 3
        assert db.scalar(select(func.count(UserActionLog.id))) == 3


@pytest.mark.parametrize("kind", ["offer", "shop"])
@pytest.mark.parametrize("override_auth", [False, True])
def test_click_lock_precedes_auth_and_db_dependencies(click_env, kind, override_auth):
    auth_calls, checkouts = [], []
    engine = click_env.sessions.kw["bind"]

    def checked_out(*args):
        checkouts.append(True)

    def auth_override(db: Session = Depends(get_db)):
        auth_calls.append(True)
        return db.get(User, click_env.user_id)

    if override_auth:
        click_env.app.dependency_overrides[get_current_user] = auth_override
    event.listen(engine, "checkout", checked_out)
    key = _key(click_env, kind)
    async def run():
        async with click_env.client() as client:
            async with click_locks.hold(key):
                pending = asyncio.create_task(client.post(_path(click_env, kind), headers={"Authorization": f"Bearer {click_env.raw_token}"}))
                await _wait_until(lambda: len(click_locks._queues[key]) == 2)
                assert not click_env.created_sessions
                assert not checkouts
                assert not auth_calls
            response = await asyncio.wait_for(pending, 3)
            assert response.status_code == 200 and response.json()["recorded"]
    try:
        asyncio.run(run())
    finally:
        event.remove(engine, "checkout", checked_out)
    assert checkouts
    assert len(click_env.created_sessions) == 1
    assert len(auth_calls) == int(override_auth)
    with click_env.sessions() as db:
        assert db.get(User, click_env.user_id).button_click_count == 1
        assert db.scalar(select(OfferClick.user_id)) == click_env.user_id
        assert db.scalar(select(UserActionLog.user_id)) == click_env.user_id


def test_waiting_request_uses_fresh_sliding_window_time(click_env, monkeypatch):
    base = datetime.now(timezone.utc)
    current_time = [base + timedelta(seconds=30)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current_time[0]

    with click_env.sessions() as db:
        offer = db.get(Offer, click_env.offer_ids[0])
        offer.click_count = 1
        db.add(OfferClick(offer_id=offer.id, shop_id=offer.shop_id, ip_hash=_key(click_env, "offer")[2], created_at=base))
        db.commit()
    monkeypatch.setattr(public, "datetime", Clock)
    key = _key(click_env, "offer")
    async def run():
        async with click_env.client() as client:
            async with click_locks.hold(key):
                pending = asyncio.create_task(client.post(_path(click_env, "offer")))
                await _wait_until(lambda: len(click_locks._queues[key]) == 2)
                current_time[0] = base + timedelta(seconds=61)
            response = await pending
            assert response.status_code == 200 and response.json()["recorded"]
            assert response.json()["click_count"] == 2
    asyncio.run(run())


@pytest.mark.parametrize("age_seconds,recorded", [(59.999, False), (60, False), (60.001, True)])
def test_sliding_window_keeps_exact_sixty_second_boundary(click_env, monkeypatch, age_seconds, recorded):
    now = datetime.now(timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    with click_env.sessions() as db:
        offer = db.get(Offer, click_env.offer_ids[0])
        offer.click_count = 7
        db.add(OfferClick(offer_id=offer.id, shop_id=offer.shop_id, ip_hash=_key(click_env, "offer")[2], created_at=now - timedelta(seconds=age_seconds)))
        db.commit()
    monkeypatch.setattr(public, "datetime", Clock)
    async def run():
        async with click_env.client() as client:
            return await client.post(_path(click_env, "offer"))
    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()["recorded"] is recorded
    assert response.json()["click_count"] == 7 + recorded


def test_returning_count_needs_no_query_or_refresh_after_commit(click_env, monkeypatch):
    with click_env.sessions() as db:
        db.execute(update(Offer).where(Offer.id == click_env.offer_ids[0]).values(click_count=7))
        db.commit()
    updates = []

    def committed(db):
        db.info["committed"] = True

    def query(state):
        assert not state.session.info.get("committed"), "request queried after commit"
        if _is_offer_update(state):
            updates.append(str(state.statement))

    def refresh(*args, **kwargs):
        raise AssertionError("click handler must not refresh")

    event.listen(click_env.sessions.class_, "after_commit", committed)
    event.listen(click_env.sessions.class_, "do_orm_execute", query)
    monkeypatch.setattr(click_env.sessions.class_, "refresh", refresh)
    async def run():
        async with click_env.client() as client:
            return await client.post(_path(click_env, "offer"))
    try:
        response = asyncio.run(run())
    finally:
        event.remove(click_env.sessions.class_, "after_commit", committed)
        event.remove(click_env.sessions.class_, "do_orm_execute", query)
    assert response.status_code == 200 and response.json()["click_count"] == 8
    assert len(updates) == 1 and "RETURNING offers.click_count" in updates[0]
    with click_env.sessions() as db:
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 8
        assert db.scalar(select(func.count(OfferClick.id))) == 1
        assert db.scalar(select(func.count(UserActionLog.id))) == 1


@pytest.mark.parametrize("kind", ["offer", "shop"])
def test_log_failure_rolls_back_count_click_and_user_activity(click_env, kind):
    with click_env.sessions() as db:
        user = db.get(User, click_env.user_id)
        baseline = (user.button_click_count, user.total_duration_seconds, user.last_active_at)
        activity_baseline = db.get(UserSession, _session_token_digest(click_env.raw_token)).last_active_at

    def fail_log(db, *_):
        if db.info.get("request_id") == "fail" and any(isinstance(obj, UserActionLog) for obj in db.new):
            raise RuntimeError("simulated action log failure")

    event.listen(click_env.sessions.class_, "before_flush", fail_log)
    async def run():
        async with click_env.client(raise_app_exceptions=False) as client:
            return await client.post(_path(click_env, kind), headers={"X-Test-Request": "fail", "Authorization": f"Bearer {click_env.raw_token}"})
    try:
        response = asyncio.run(run())
    finally:
        event.remove(click_env.sessions.class_, "before_flush", fail_log)
    assert response.status_code == 500
    with click_env.sessions() as db:
        assert db.scalar(select(func.count(OfferClick.id))) == 0
        assert db.scalar(select(func.count(UserActionLog.id))) == 0
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 0
        user = db.get(User, click_env.user_id)
        assert (user.button_click_count, user.total_duration_seconds, user.last_active_at) == baseline
        assert db.get(UserSession, _session_token_digest(click_env.raw_token)).last_active_at == activity_baseline


def test_cancelled_waiter_does_not_run_auth_or_leave_a_key(click_env):
    key = _key(click_env, "offer")
    async def run():
        async with click_env.client() as client:
            async with click_locks.hold(key):
                cancelled = asyncio.create_task(client.post(_path(click_env, "offer"), headers={"Authorization": f"Bearer {click_env.raw_token}"}))
                await _wait_until(lambda: len(click_locks._queues[key]) == 2)
                cancelled.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await cancelled
                assert not click_env.created_sessions
                assert len(click_locks._queues[key]) == 1
            assert key not in click_locks._queues
            response = await client.post(_path(click_env, "offer"))
            assert response.status_code == 200 and response.json()["recorded"]
    asyncio.run(run())


def test_cancelled_running_request_keeps_key_until_sync_transaction_finishes(click_env):
    entered, release, committed = threading.Event(), threading.Event(), threading.Event()
    follower_sql = threading.Event()

    def delay_update(state):
        request_id = state.session.info.get("request_id")
        if request_id == "cancelled-owner" and _is_offer_update(state):
            entered.set()
            assert release.wait(timeout=5), "cancelled owner watchdog expired"
        elif request_id == "follower":
            follower_sql.set()

    def after_commit(db):
        if db.info.get("request_id") == "cancelled-owner":
            committed.set()

    event.listen(click_env.sessions.class_, "do_orm_execute", delay_update)
    event.listen(click_env.sessions.class_, "after_commit", after_commit)
    async def run():
        async with click_env.client() as client:
            owner = asyncio.create_task(client.post(
                _path(click_env, "offer"),
                headers={"X-Test-Request": "cancelled-owner", "X-Forwarded-For": "198.51.100.71"},
            ))
            follower = None
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                owner.cancel()
                follower = asyncio.create_task(client.post(
                    _path(click_env, "offer"),
                    headers={"X-Test-Request": "follower", "X-Forwarded-For": "198.51.100.71"},
                ))
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.shield(follower), 0.3)
                assert not follower_sql.is_set(), "cancelled owner released the key while its DB worker was running"
                assert not owner.done(), "request cleanup must wait for the running transaction"
            finally:
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(owner, 3)
                assert await asyncio.to_thread(committed.wait, 3)
                if follower is not None:
                    response = await asyncio.wait_for(follower, 3)
                    assert response.status_code == 200 and response.json()["recorded"] is False
    try:
        asyncio.run(run())
    finally:
        event.remove(click_env.sessions.class_, "do_orm_execute", delay_update)
        event.remove(click_env.sessions.class_, "after_commit", after_commit)
    with click_env.sessions() as db:
        assert db.get(Offer, click_env.offer_ids[0]).click_count == 1
        assert db.scalar(select(func.count(OfferClick.id))) == 1
        assert db.scalar(select(func.count(UserActionLog.id))) == 1


def test_key_registry_releases_after_holder_failure_and_waiter_cancellation():
    locks = ClickLocks()
    key = ("offer-click", "1", "hash")
    async def run():
        entered = asyncio.Event()
        async def waiting():
            async with locks.hold(key):
                entered.set()
        with pytest.raises(ValueError):
            async with locks.hold(key):
                cancelled = asyncio.create_task(waiting())
                successor = asyncio.create_task(waiting())
                await _wait_until(lambda: len(locks._queues[key]) == 3)
                cancelled.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await cancelled
                assert len(locks._queues[key]) == 2
                raise ValueError("holder failed")
        await asyncio.wait_for(successor, 3)
        assert entered.is_set()
        assert not locks._queues
    asyncio.run(run())
