from app.main import VERSION, app, health


def test_api_reports_release_version():
    assert VERSION == "3.7.6"
    assert app.version == VERSION
    assert health() == {"status": "ok", "version": VERSION}
