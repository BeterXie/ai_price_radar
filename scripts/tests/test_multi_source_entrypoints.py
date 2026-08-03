from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_refresh_entrypoints_use_atomic_multi_source_publisher():
    for relative_path in ("scripts/crawl_and_publish.sh", "scripts/refresh_remote.sh"):
        script = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "publish_catalog.py" in script
        assert "--ldxp-db" in script
        assert "--dujiao-db" in script
        assert "sync_ldxp.py" not in script


def test_remote_crawler_mounts_and_runs_dujiao_discovery_seeds():
    compose = (ROOT / "docker-compose.pricememo.yml").read_text(encoding="utf-8")
    refresh = (ROOT / "scripts/refresh_remote.sh").read_text(encoding="utf-8")
    assert "dujiao_seeds.txt:/config/dujiao_seeds.txt:ro" in compose
    assert "discover-dujiao" in refresh
    assert "--max-new-candidates" in refresh
    assert "--max-processed-candidates" in refresh


def test_source_detector_has_no_database_network_or_credentials():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    detector = compose.split("  source-detector:\n", 1)[1].split("\n  web:\n", 1)[0]
    assert "DATABASE_URL" not in detector
    assert "detector_control:" in detector
    assert "detector_egress:" in detector
    assert "default:" not in detector
    assert 'cap_drop: ["ALL"]' in detector
    assert 'security_opt: ["no-new-privileges:true"]' in detector
    assert "docker.sock" not in detector
    assert "detector_control:\n    internal: true" in compose

    dockerfile = (ROOT / "detector" / "Dockerfile").read_text(encoding="utf-8")
    assert "USER detector" in dockerfile
