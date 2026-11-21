import os
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from scripts.migrate_qq_groups_v27 import migrate


@pytest.mark.parametrize("database_url", [
    "sqlite://",
    pytest.param(os.getenv("TEST_POSTGRES_URL", ""), marks=pytest.mark.skipif(
        not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")),
])
def test_repeatable_group_migration_preserves_settings_and_separates_bot_accounts(database_url):
    engine = create_engine(database_url)
    migrate(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO qq_group_subscriptions(app_id, group_openid, subscribed) VALUES ('bot-a', 'group', true)"))
    migrate(engine)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT subscribed FROM qq_group_subscriptions")).scalar() == 1
        connection.execute(text("INSERT INTO qq_group_subscriptions(app_id, group_openid) VALUES ('bot-b', 'group')"))
        assert connection.execute(text("SELECT subscribed FROM qq_group_subscriptions WHERE app_id='bot-b'")).scalar() == 0
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO qq_group_subscriptions(app_id, group_openid) VALUES ('bot-a', 'group')"))
    assert "bot_token" not in {column["name"] for column in inspect(engine).get_columns("qq_group_subscriptions")}
    engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_postgres_group_events_use_database_timestamps_and_persist_across_sessions(monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.models import QQGroupSubscription
    from extensions.bots import group_push
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    migrate(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(group_push, "SessionLocal", factory)
    for event, second in [("GROUP_MSG_RECEIVE", 1), ("GROUP_MSG_REJECT", 2), ("GROUP_MSG_RECEIVE", 1)]:
        group_push.apply_group_event("pg-event-bot", event, {"group_openid": "event-group", "timestamp": 1795244400 + second})
    with factory() as db:
        row = db.query(QQGroupSubscription).filter_by(app_id="pg-event-bot").one()
        assert not row.subscribed and row.allow_proactive is False
        assert row.last_event_at.tzinfo is not None
    engine.dispose()


def test_model_first_creation_has_same_sql_defaults_as_migration():
    from app.models import QQGroupSubscription
    engine = create_engine("sqlite://")
    QQGroupSubscription.__table__.create(engine)
    migrate(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO qq_group_subscriptions(app_id, group_openid) VALUES ('model-first', 'group')"))
        row = connection.execute(text("SELECT subscribed, is_member, state_version, created_at, updated_at FROM qq_group_subscriptions")).one()
        assert tuple(row[:3]) == (0, 1, 0)
        assert row[3] and row[4]
    engine.dispose()
