import json
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
    assert render(result) == result
    with pytest.raises(ValueError):
        render("unrelated.example { respond 200 }")


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
