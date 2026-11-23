from scripts.collector_schedule import collector_release


def test_host_release_uses_the_configured_worker_version(tmp_path):
    (tmp_path / "VERSION").write_text("3.9.106")
    (tmp_path / ".env").write_text('COLLECTOR_RELEASE="3.9.105"\n')
    assert collector_release(tmp_path) == "3.9.105"
    (tmp_path / ".env").write_text("COLLECTOR_RELEASE=\n")
    assert collector_release(tmp_path) == "3.9.106"
