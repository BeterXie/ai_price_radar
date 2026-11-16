import json
from pathlib import Path

from app.main import VERSION, app, health


def test_api_reports_release_version():
    root = Path(__file__).resolve().parents[3]
    assert VERSION == (root / "VERSION").read_text(encoding="utf-8").strip()
    for name in ("package.json", "package-lock.json"):
        package = json.loads((root / "apps" / "web" / name).read_text(encoding="utf-8"))
        assert package["version"] == VERSION
        if name == "package-lock.json":
            assert package["packages"][""]["version"] == VERSION
    assert app.version == VERSION
    assert health() == {"status": "ok", "version": VERSION}
