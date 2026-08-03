import signal
import time

import pytest

import worker


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="production detector runs on Linux")
def test_probe_timeout_includes_blocking_resolver_time(monkeypatch):
    monkeypatch.setattr(worker, "probe_source", lambda _url: time.sleep(1))
    started_at = time.monotonic()
    with pytest.raises(TimeoutError, match="total time limit"):
        worker._probe_with_timeout("https://slow.example", timeout_seconds=0.01)
    assert time.monotonic() - started_at < 0.5
