"""Shared process-level pacing for the explicitly configured collection origin."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import time


class OriginCoolingDown(Exception):
    """Local pacing, not proof that a source is invalid."""


class PacingStorageError(OriginCoolingDown):
    """Local infrastructure fault; collectors must abort the batch."""


def _persist(root, state):
    try:
        temporary = root / "16688.tmp"
        with temporary.open('w') as stream:
            stream.write(json.dumps(state))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(root / "16688.json")
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise PacingStorageError("16688 local pacing storage unavailable") from exc


@contextmanager
def origin_budget(host: str, timeout: float = 45):
    directory = os.getenv("COLLECTOR_RATE_DIR", "")
    if not directory or host.casefold() not in {"16688.com.cn", "www.16688.com.cn"}:
        yield lambda status, **kwargs: None
        return
    import fcntl
    root = Path(directory)
    try:
        root.mkdir(parents=True, exist_ok=True)
        lock_file = (root / "16688.lock").open("a+")
    except OSError as exc:
        raise PacingStorageError("16688 local pacing storage unavailable") from exc
    # A fixed filename avoids arbitrary paths from upstream DNS names.
    with lock_file as lock:
        deadline = time.monotonic() + min(10.0, timeout)
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise OriginCoolingDown("16688 pacing busy; retry after 15 minutes")
                time.sleep(min(.1, max(0, deadline-time.monotonic())))
            except OSError as exc:
                raise PacingStorageError("16688 local pacing lock unavailable") from exc
        state_path = root / "16688.json"
        try:
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            if not isinstance(state, dict) or any(type(value) not in (float, int) or not math.isfinite(value) for value in state.values()):
                raise ValueError("invalid pacing state")
        except (ValueError, OSError) as exc:
            raise PacingStorageError("16688 pacing state unavailable; retry later") from exc
        now = time.time()
        if state.get("blocked_until", 0) > now:
            raise OriginCoolingDown("16688 cooling down; retry after 15 minutes")
        interval = 5.0 if os.getenv('COLLECTOR_16688_PROXY_KEY_FILE') else 2.0
        delay = min(interval, max(0.0, state.get("last_request", 0) + interval - now))
        if delay:
            if delay > deadline-time.monotonic():
                raise OriginCoolingDown("16688 pacing deadline exceeded")
            time.sleep(delay)
        state["last_request"] = time.time()
        _persist(root, state)
        def status_received(status, *, allow_failover=False):
            state['last_request'] = time.time()
            if status in (0, 403, 429, 520) and not (status == 520 and allow_failover):
                state["blocked_until"] = time.time() + 15 * 60
                _persist(root, state)
                detail = f'response {status}' if status else 'proxy unavailable'
                raise OriginCoolingDown(f"16688 {detail}; cooling down")
            _persist(root, state)
        yield status_received
