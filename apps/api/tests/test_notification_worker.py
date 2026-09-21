from __future__ import annotations

import sys

import pytest
from app import notification_worker


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_worker(monkeypatch, process_once_impl, sleeps: list[float]) -> None:
    monkeypatch.setattr(notification_worker, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(notification_worker, "process_once", process_once_impl)
    monkeypatch.setattr(notification_worker, "get_settings", lambda: None)
    monkeypatch.setattr(notification_worker.time, "sleep", sleeps.append)


def test_worker_once_returns_zero_on_success(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_process_once(db, *, limit):
        calls.append(limit)
        return 3

    _patch_worker(monkeypatch, fake_process_once, sleeps)
    monkeypatch.setattr(sys, "argv", ["notification_worker", "--once", "--batch-size", "5"])

    assert notification_worker.main() == 0
    assert calls == [5]
    assert sleeps == []


def test_worker_once_returns_one_on_failure(monkeypatch):
    sleeps: list[float] = []

    def fake_process_once(db, *, limit):
        raise RuntimeError("database unavailable")

    _patch_worker(monkeypatch, fake_process_once, sleeps)
    monkeypatch.setattr(sys, "argv", ["notification_worker", "--once"])

    # A crash loop in cron/supervisor one-shot mode is now a clean exit code.
    assert notification_worker.main() == 1
    assert sleeps == []


class _StopLoop(BaseException):
    pass


def test_worker_loop_backs_off_after_transient_failures(monkeypatch):
    sleeps: list[float] = []
    calls = {"n": 0}

    def fake_process_once(db, *, limit):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")
        if calls["n"] == 2:
            raise RuntimeError("db still down")
        if calls["n"] == 3:
            return 0  # recovered; backoff counter must reset
        raise _StopLoop

    _patch_worker(monkeypatch, fake_process_once, sleeps)
    monkeypatch.setattr(sys, "argv", ["notification_worker", "--poll-seconds", "15"])

    with pytest.raises(_StopLoop):
        notification_worker.main()

    # Two escalating backoffs while failing, then the normal poll interval.
    assert sleeps == [15, 30, 15]


def test_worker_loop_backoff_is_capped(monkeypatch):
    sleeps: list[float] = []
    calls = {"n": 0}

    def fake_process_once(db, *, limit):
        calls["n"] += 1
        if calls["n"] <= 40:
            raise RuntimeError("persistent outage")
        raise _StopLoop

    _patch_worker(monkeypatch, fake_process_once, sleeps)
    monkeypatch.setattr(sys, "argv", ["notification_worker", "--poll-seconds", "15"])

    with pytest.raises(_StopLoop):
        notification_worker.main()

    assert sleeps[0] == 15
    assert max(sleeps) == notification_worker.MAX_BACKOFF_SECONDS
    # Once capped, the worker keeps polling at the cap instead of growing forever.
    assert sleeps[-1] == notification_worker.MAX_BACKOFF_SECONDS
