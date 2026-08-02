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
