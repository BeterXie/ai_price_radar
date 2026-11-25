import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import TimeoutError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.database import Base
from app.models import User, UserBotBinding
from extensions.bots import chat_commands, group_push, qq_gateway


@pytest.fixture
def bindings(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(qq_gateway, "SessionLocal", factory)
    monkeypatch.delenv("QQ_BOT_APP_ID", raising=False)
    monkeypatch.delenv("QQ_BOT_APP_SECRET", raising=False)
    with factory() as db:
        user = User(email="gateway@example.test")
        db.add(user)
        db.flush()
        db.add(UserBotBinding(user_id=user.id, target_id="target-a", bot_token="secret-a",
                              extra_meta={"app_id": "bot-a"}, is_active=False))
        db.commit()
    yield factory
    engine.dispose()


async def monitor_once(service, monkeypatch):
    original_sleep = asyncio.sleep

    async def end_iteration(_seconds):
        service.running = False
        await original_sleep(0)

    with monkeypatch.context() as patch:
        patch.setattr(qq_gateway.asyncio, "sleep", end_iteration)
        service.running = True
        await service._monitor_loop()


async def idle_gateway(*_args):
    await asyncio.Future()


def test_paused_push_stays_connected_and_can_resume_from_chat(bindings, monkeypatch):
    factory = bindings
    service = qq_gateway.QQGatewayService()
    monkeypatch.setattr(service, "_run_bot_gateway", idle_gateway)
    monkeypatch.setattr(qq_gateway, "_is_bot_enabled", lambda: True)
    replies = []

    def handle(raw_text, sender_id, **_kwargs):
        with factory() as db:
            return chat_commands.toggle_user_preference(db, sender_id, raw_text)

    monkeypatch.setattr(qq_gateway, "handle_chat_command", handle)
    monkeypatch.setattr(service.bot_client, "send_c2c_message", lambda **kw: replies.append(kw) or True)

    async def run():
        await monitor_once(service, monkeypatch)
        connection = service._bot_tasks["bot-a"]
        assert not connection.done()
        with factory() as db:
            assert group_push.bot_credentials(db) == {}
            assert group_push.bot_credentials(db, active_only=False) == {"bot-a": "secret-a"}
        queue = asyncio.Queue()
        service._enqueue_message(queue, "恢复推送", "target-a", "", "message-a")
        worker = asyncio.create_task(service._reply_worker(queue, "bot-a", "secret-a"))
        try:
            await asyncio.wait_for(queue.join(), timeout=3)
            with factory() as db:
                assert db.scalar(select(UserBotBinding)).is_active
                assert group_push.bot_credentials(db) == {"bot-a": "secret-a"}
            await monitor_once(service, monkeypatch)
            assert service._bot_tasks["bot-a"] is connection
            assert "已为您恢复消息推送" in replies[0]["text"]
            assert replies[0]["msg_id"] == "message-a"
        finally:
            worker.cancel()
            await service.stop()
            await asyncio.gather(worker, connection, return_exceptions=True)

    asyncio.run(run())


def test_temporary_database_failure_preserves_connection_but_unbind_removes_it(bindings, monkeypatch):
    service = qq_gateway.QQGatewayService()
    monkeypatch.setattr(service, "_run_bot_gateway", idle_gateway)

    def unavailable():
        raise TimeoutError("database pool exhausted")

    async def run():
        await monitor_once(service, monkeypatch)
        connection = service._bot_tasks["bot-a"]
        try:
            with monkeypatch.context() as patch:
                patch.setattr(qq_gateway, "SessionLocal", unavailable)
                await monitor_once(service, patch)
            assert service._bot_tasks["bot-a"] is connection
            assert not connection.done()
            assert service._bot_credentials == {"bot-a": "secret-a"}
            with bindings() as db:
                db.delete(db.scalar(select(UserBotBinding)))
                db.commit()
            await monitor_once(service, monkeypatch)
            assert service._bot_tasks == {}
            assert service._bot_credentials == {}
            assert connection.cancelled()
        finally:
            await service.stop()
            await asyncio.gather(connection, return_exceptions=True)

    asyncio.run(run())


def test_paused_bot_credential_rotation_reconnects_only_that_bot(bindings, monkeypatch):
    service = qq_gateway.QQGatewayService()
    monkeypatch.setattr(service, "_run_bot_gateway", idle_gateway)

    async def run():
        await monitor_once(service, monkeypatch)
        old_connection = service._bot_tasks["bot-a"]
        with bindings() as db:
            db.scalar(select(UserBotBinding)).bot_token = "rotated-secret"
            db.commit()
        await monitor_once(service, monkeypatch)
        new_connection = service._bot_tasks["bot-a"]
        try:
            assert old_connection.cancelled()
            assert new_connection is not old_connection and not new_connection.done()
            assert service._bot_credentials["bot-a"] == "rotated-secret"
        finally:
            await service.stop()
            await asyncio.gather(old_connection, new_connection, return_exceptions=True)

    asyncio.run(run())


def test_unreadable_credential_does_not_disconnect_other_bindings(bindings, monkeypatch):
    with bindings() as db:
        user = User(email="broken@example.test")
        db.add(user)
        db.flush()
        db.add(UserBotBinding(user_id=user.id, target_id="target-b", bot_token="broken",
                              extra_meta={"app_id": "bot-b"}, is_active=True))
        db.commit()

    def decrypt(value):
        if value == "broken":
            raise RuntimeError("stored credential cannot be decrypted")
        return value

    monkeypatch.setattr(group_push, "decrypt_secret", decrypt)
    with bindings() as db:
        assert group_push.bot_credentials(db, active_only=False) == {"bot-a": "secret-a"}
        assert group_push.bot_credentials(db) == {}


@pytest.mark.parametrize("metadata", [["app_id", "bot-b"], "bot-b", {"app_id": ["bot-b"]}])
def test_invalid_paused_metadata_does_not_block_other_bindings(bindings, metadata):
    with bindings() as db:
        user = User(email="invalid@example.test")
        db.add(user)
        db.flush()
        db.add(UserBotBinding(user_id=user.id, target_id="target-b", bot_token="secret-b",
                              extra_meta=metadata, is_active=False))
        db.commit()
        assert group_push.bot_credentials(db, active_only=False) == {"bot-a": "secret-a"}


@pytest.mark.parametrize("all_paused", [False, True])
def test_duplicate_app_credentials_have_stable_preference(bindings, all_paused):
    with bindings() as db:
        original = db.scalar(select(UserBotBinding))
        original.is_active = not all_paused
        original.updated_at = datetime(2026, 11, 20, tzinfo=timezone.utc)
        for suffix, active, day in (("active-new", not all_paused, 21), ("paused-newest", False, 22)):
            user = User(email=suffix + "@example.test")
            db.add(user)
            db.flush()
            db.add(UserBotBinding(user_id=user.id, target_id=suffix, bot_token=suffix,
                                  extra_meta={"app_id": "bot-a"}, is_active=active,
                                  updated_at=datetime(2026, 11, day, tzinfo=timezone.utc)))
        db.commit()
        expected = "paused-newest" if all_paused else "active-new"
        assert group_push.bot_credentials(db, active_only=False) == {"bot-a": expected}
        assert group_push.bot_credentials(db) == ({} if all_paused else {"bot-a": expected})


@pytest.mark.parametrize("active", [False, True])
def test_environment_precedes_paused_credentials_but_not_active_binding(bindings, monkeypatch, active):
    monkeypatch.setenv("QQ_BOT_APP_ID", "bot-a")
    monkeypatch.setenv("QQ_BOT_APP_SECRET", "environment-secret")
    with bindings() as db:
        db.scalar(select(UserBotBinding)).is_active = active
        db.commit()
        expected = {"bot-a": "secret-a" if active else "environment-secret"}
        assert group_push.bot_credentials(db, active_only=False) == expected
        assert group_push.bot_credentials(db) == expected
