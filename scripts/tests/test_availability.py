import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from check_memory_budget import available_mib
from render_production_proxy import render
import check_availability


def test_memory_guard_requires_reclaimable_headroom():
    assert available_mib("MemFree: 100 kB\nMemAvailable: 1126400 kB\n") == 1100
    with pytest.raises(ValueError):
        available_mib("MemFree: 9999999 kB\n")


def test_proxy_patch_preserves_unrelated_routes_and_is_idempotent():
    source = """other.example {
    reverse_proxy app:8080
}
ai.pricememo.cn, pricememo.cn {
    @api path /api/* /docs* /openapi.json /health
    reverse_proxy ai-radar-api:8000
    reverse_proxy ai-radar-web:3000
    log { output file /data/caddy-logs/access.json }
}
aiprice.si {
    import brand_site ai-radar-aiprice
}
"""
    result = render(source)
    assert "reverse_proxy app:8080" in result
    assert "output file /data/caddy-logs/access.json" in result
    assert "reverse_proxy 172.18.0.2:8000" in result
    assert "reverse_proxy 172.18.0.4:3000" in result
    assert "import brand_site 172.18.0.8" in result
    assert "/data/v1/catalogs/*" in result
    assert "/data/alerts-latest.json" in result
    assert render(result) == result
    with pytest.raises(ValueError):
        render("unrelated.example { respond 200 }")


def test_proxy_adds_new_feed_before_existing_trailing_comment():
    source = """ai.pricememo.cn {
    @api path /api/* /health /data/latest.json # existing feeds
    reverse_proxy 172.18.0.2:8000
    reverse_proxy 172.18.0.4:3000
}
"""
    result = render(source)
    matcher = next(line for line in result.splitlines() if "@api" in line)
    assert "/data/alerts-latest.json" in matcher.split("#")[0]
    assert render(result) == result


def test_host_monitor_detects_restart_and_oom_without_flagging_a_new_release(monkeypatch):
    class FakePath:
        def __init__(self, value):
            pass
        def read_text(self):
            return "MemAvailable: 1500000 kB\n"
    monkeypatch.setattr(check_availability, "Path", FakePath)
    item = {"Name": "/web", "Id": "same", "RestartCount": 2, "State": {"Running": True, "Health": {"Status": "healthy"}}}
    monkeypatch.setattr(check_availability, "command", lambda cmd: json.dumps([item]) if cmd[0] == "docker" else "Out of memory: Killed process 123")
    _, errors = check_availability.inspect_host({"containers": {"web": {"id": "same", "restarts": 1}}}, 1000)
    assert any("restarted" in error for error in errors)
    assert any("Kernel killed" in error for error in errors)
    item["Id"] = "new-release"
    monkeypatch.setattr(check_availability, "command", lambda cmd: json.dumps([item]) if cmd[0] == "docker" else "")
    _, errors = check_availability.inspect_host({"containers": {"web": {"id": "same", "restarts": 1}}}, 1000)
    assert errors == []


@pytest.mark.parametrize('journal,count', [
    ('oom-kill:constraint=CONSTRAINT_MEMCG,task=uvicorn,pid=123', 1),
    ('oom-kill:constraint=CONSTRAINT_MEMCG,pid=123\nMemory cgroup out of memory: Killed process 123', 1),
    ('oom-kill:constraint=CONSTRAINT_MEMCG,pid=123\noom-kill:constraint=CONSTRAINT_MEMCG,pid=124', 2),
    ('oom-kill:constraint=CONSTRAINT_MEMCG,pid=123\nOut of memory: Killed process 124\n'
     'oom-kill:constraint=CONSTRAINT_MEMCG,pid=125\nMemory cgroup out of memory: Killed process 125', 3),
    ('uvicorn invoked oom-killer', 0),
])
def test_cgroup_oom_is_counted_once_per_victim(monkeypatch, journal, count):
    class FakePath:
        def __init__(self, value):
            pass
        def read_text(self):
            return 'MemAvailable: 1500000 kB\n'
    monkeypatch.setattr(check_availability, 'Path', FakePath)
    monkeypatch.setattr(check_availability, 'command', lambda cmd: '[]' if cmd[0] == 'docker' else journal)
    report, errors = check_availability.inspect_host({}, 1000)
    assert report['oom_kills'] == count
    assert bool(errors) == bool(count)


@pytest.mark.parametrize('timestamp', ['2026-11-19T15:59:08.077349+00:00', '2026-11-19T15:59:08Z', '2026-11-19T23:59:08+08:00'])
def test_snapshot_age_uses_publication_time_not_file_mtime(tmp_path, timestamp):
    pointer = tmp_path / 'latest.json'
    pointer.write_text(json.dumps({'snapshot_id': '9090', 'published_at': timestamp}), encoding='utf-8')
    published = datetime(2026, 11, 19, 15, 59, 8, tzinfo=timezone.utc).timestamp()
    report, errors = check_availability.inspect_snapshot(pointer, published + 60)
    assert report['snapshot_id'] == '9090' and report['snapshot_age_seconds'] == 60
    assert errors == []
    _, errors = check_availability.inspect_snapshot(pointer, published + 7201)
    assert any('No published snapshot' in error for error in errors)
    _, errors = check_availability.inspect_snapshot(pointer, published - 600)
    assert any('future' in error for error in errors)


def test_invalid_snapshot_is_not_reported_as_fresh(tmp_path):
    pointer = tmp_path / 'latest.json'
    pointer.write_text(json.dumps({'snapshot_id': '9090', 'published_at': 'invalid'}), encoding='utf-8')
    with pytest.raises(ValueError, match='timestamp'):
        check_availability.inspect_snapshot(pointer, 1000)
