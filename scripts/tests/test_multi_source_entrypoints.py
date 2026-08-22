from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_refresh_entrypoints_use_atomic_multi_source_publisher():
    for relative_path in ("scripts/crawl_and_publish.sh", "scripts/refresh_remote.sh"):
        script = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "publish_catalog.py" in script
        assert "--ldxp-db" in script
        assert "--dujiao-db" in script
        assert "sync_ldxp.py" not in script


def test_remote_refresh_uses_dedicated_importer_image():
    refresh = (ROOT / "scripts" / "refresh_remote.sh").read_text(encoding="utf-8")
    publish_block = refresh.split("PUBLISH_ARGS=(", 1)[1]
    assert "ai-price-radar-importer" in publish_block
    assert "ai-price-radar-api" not in publish_block
    assert '-v "$ROOT:/workspace:ro"' in publish_block
    assert "build_crawler_publish_db.py" in refresh
    assert "PRAGMA quick_check" not in refresh
    assert 'sqlite3 "$CRAWLER_DB" ".backup' not in refresh
    assert '-v "$PUBLISH_DB:/tmp/ldxp_publish.db:ro"' in publish_block
    assert "-w /workspace/pipeline" in publish_block

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    importer = compose.split("  importer:\n", 1)[1].split("\nvolumes:\n", 1)[0]
    assert "image: ai-price-radar-importer" in importer

    quick_deploy = (ROOT / "docs" / "QUICK_DEPLOY.md").read_text(encoding="utf-8")
    assert "$COMPOSE build importer" in quick_deploy


def test_inventory_refresh_carries_other_sources_forward():
    refresh = (ROOT / "scripts" / "refresh_remote.sh").read_text(encoding="utf-8")
    inventory_publish = refresh.split('if [[ "$MODE" == "inventory" ]]', 1)[1]
    inventory_publish = inventory_publish.split("else", 1)[0]
    assert "python sync_source.py" in inventory_publish
    assert "--connector ldxp" in inventory_publish
    assert "--source /tmp/ldxp_publish.db" in inventory_publish


def test_remote_browser_scans_have_a_per_shop_hard_timeout():
    refresh = (ROOT / "scripts" / "refresh_remote.sh").read_text(encoding="utf-8")
    assert refresh.count("--shop-timeout 120") == 3


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
