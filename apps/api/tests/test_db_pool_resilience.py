"""Regression tests for the connection-pool starvation incident.

Production ran with SQLAlchemy's default QueuePool (size 5, overflow 10,
timeout 30s). Every sync endpoint holds one anyio worker thread while it waits
for a connection, so once the pool saturated, all 40 workers parked on
``QueuePool._do_get`` and ``/health`` — which touches no database at all —
timed out too. These tests pin the three fixes:

1. the pool timeout is short enough to fail fast instead of parking a worker;
2. ``get_db`` rolls back on error so no connection returns to the pool with an
   open transaction (the ``idle in transaction`` rows that held the pool);
3. the current-snapshot pointer is cached, so the hottest public read stops
   costing one round trip per request.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import get_db
from app.models import Base, CatalogSnapshot
from app.services.catalog import (
    clear_current_snapshot_cache,
    get_current_snapshot,
)


@pytest.fixture(autouse=True)
def _clear_snapshot_cache():
    clear_current_snapshot_cache()
    yield
    clear_current_snapshot_cache()


def _sqlite_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_pool_timeout_stays_under_the_worker_budget():
    """A pool wait must not consume a worker thread for the old 30 seconds."""
    settings = get_settings()
    assert settings.db_pool_timeout_seconds <= 10
    assert settings.db_pool_timeout_seconds < 30
    assert settings.db_pool_size >= 1
    assert settings.db_pool_max_overflow >= 0


def test_postgres_engine_uses_configured_pool_limits(monkeypatch):
    """The pool knobs reach create_engine for non-SQLite URLs."""
    settings = get_settings()
    monkeypatch.setattr(settings, "db_pool_size", 7)
    monkeypatch.setattr(settings, "db_pool_max_overflow", 3)
    monkeypatch.setattr(settings, "db_pool_timeout_seconds", 2.5)
    monkeypatch.setattr(settings, "db_pool_recycle_seconds", 900)

    # Re-import the module so module-level engine construction reruns.
    import importlib

    import app.database as database

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@localhost:5432/db")
    reloaded = importlib.reload(database)
    try:
        pool = reloaded.engine.pool
        assert pool.size() == 7
        assert pool._max_overflow == 3
        assert pool._timeout == 2.5
        assert pool._recycle == 900
    finally:
        monkeypatch.undo()
        importlib.reload(database)


def test_get_db_rolls_back_when_the_endpoint_raises():
    """A failing endpoint must not return a connection with an open transaction."""
    session = _sqlite_session()
    session.add(CatalogSnapshot(source="rollback", published_at=datetime.now(timezone.utc)))
    session.commit()

    closed: list[bool] = []

    class _TrackingSession:
        def __init__(self, inner: Session) -> None:
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def rollback(self) -> None:
            closed.append(True)
            self._inner.rollback()

        def close(self) -> None:
            self._inner.close()

    import app.database as database

    original = database.SessionLocal
    database.SessionLocal = lambda: _TrackingSession(session)
    try:
        generator = get_db()
        next(generator)
        with pytest.raises(RuntimeError):
            generator.throw(RuntimeError("endpoint exploded"))
    finally:
        database.SessionLocal = original

    assert closed == [True], "get_db must roll back before closing on error"


def test_current_snapshot_cache_serves_repeated_lookups_without_a_query():
    """The second lookup inside the TTL must not hit the database again."""
    db = _sqlite_session()
    db.add(CatalogSnapshot(source="older", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db.add(CatalogSnapshot(source="newest", published_at=datetime(2026, 2, 1, tzinfo=timezone.utc)))
    db.commit()

    first = get_current_snapshot(db)
    assert first is not None and first.source == "newest"

    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    from sqlalchemy import event

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _record)
    try:
        second = get_current_snapshot(db)
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert second is not None and second.source == "newest"
    assert statements == [], "cached lookup must not issue SQL"


def test_current_snapshot_cache_expires_and_returns_detached_rows():
    """After the TTL the cache re-reads and never hands back a bound instance."""
    db = _sqlite_session()
    db.add(CatalogSnapshot(source="first", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db.commit()

    first = get_current_snapshot(db)
    assert first is not None
    # A detached copy: the cached value must not belong to the live session.
    assert first not in db

    db.add(CatalogSnapshot(source="second", published_at=datetime(2026, 3, 1, tzinfo=timezone.utc)))
    db.commit()

    # Still inside the default TTL, so the pointer is intentionally stale.
    assert get_current_snapshot(db).source == "first"

    settings = get_settings()
    original = settings.current_snapshot_cache_ttl_seconds
    settings.current_snapshot_cache_ttl_seconds = 0
    try:
        refreshed = get_current_snapshot(db)
    finally:
        settings.current_snapshot_cache_ttl_seconds = original

    assert refreshed is not None and refreshed.source == "second"


def test_current_snapshot_cache_is_isolated_per_engine():
    """Two databases in one process must not share a cached pointer."""
    db_a = _sqlite_session()
    db_a.add(CatalogSnapshot(source="a", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db_a.commit()

    db_b = _sqlite_session()
    db_b.add(CatalogSnapshot(source="b", published_at=datetime(2026, 5, 1, tzinfo=timezone.utc)))
    db_b.commit()

    assert get_current_snapshot(db_a).source == "a"
    assert get_current_snapshot(db_b).source == "b"
