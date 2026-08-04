from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler" / "ldxp"))

from ldxp_crawler.db import StateDB  # noqa: E402
from ldxp_crawler.models import ProductMatch, ShopScanResult  # noqa: E402
from scripts.purge_ldxp_raw_v11 import _sqlite_counts, _sqlite_purge  # noqa: E402


def _seed_db(path: Path) -> None:
    db = StateDB(path)
    try:
        db.upsert_candidate("TEST01", "https://pay.ldxp.cn/shop/TEST01", "seed", 100)
        run_id = db.start_run("scan", ["chatgpt"], "public_dom", {})
        db.save_scan_result(
            ShopScanResult(
                token="TEST01",
                status="success",
                scanned_item_count=1,
                matches=[
                    ProductMatch(
                        product_key="P1",
                        product_name="ChatGPT Plus",
                        matched_keywords=["chatgpt"],
                        listed_price=88.0,
                        product_status="有货",
                        product_url="https://pay.ldxp.cn/shop/TEST01/item/P1",
                        content_hash="hash-1",
                    )
                ],
            ),
            run_id,
        )
    finally:
        db.close()


def test_purge_dry_run_counts_then_apply_backs_up_and_is_idempotent(tmp_path):
    path = tmp_path / "ldxp_crawler.db"
    _seed_db(path)
    dry = _sqlite_purge(path, dry_run=True)
    assert dry["matches_raw_json"] == 1
    assert dry["snapshot_raw_json"] == 1

    applied = _sqlite_purge(path, dry_run=False, backup=True)
    assert applied["matches_raw_json"] == 1
    assert applied["backup"]
    assert Path(applied["backup"]).is_file()
    assert _sqlite_counts(path) == {"matches_raw_json": 0, "snapshot_raw_json": 0}

    second = _sqlite_purge(path, dry_run=False, backup=True)
    assert second["matches_raw_json"] == 0
