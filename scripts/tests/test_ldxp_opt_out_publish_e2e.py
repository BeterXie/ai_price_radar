from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "crawler" / "ldxp"))

from app.core.config import get_settings  # noqa: E402
from app.database import Base as ApiBase  # noqa: E402
from app.models import SourcePolicyRequest  # noqa: E402
from common import session_for  # noqa: E402
from ldxp_crawler.db import StateDB  # noqa: E402
from ldxp_crawler.models import ProductMatch, ShopScanResult  # noqa: E402
from publish_catalog import SourceSpec, publish_sources  # noqa: E402


def _seed_crawler_db(path: Path) -> None:
    db = StateDB(path)
    try:
        for token in ("TEST01", "TEST02"):
            db.upsert_candidate(token, f"https://pay.ldxp.cn/shop/{token}", "seed", 100)
            run_id = db.start_run("scan", ["chatgpt"], "public_dom", {})
            db.save_scan_result(
                ShopScanResult(
                    token=token,
                    status="success",
                    shop_name=token,
                    shop_url=f"https://pay.ldxp.cn/shop/{token}",
                    scanned_item_count=1,
                    matches=[
                        ProductMatch(
                            product_key="P1",
                            product_name="ChatGPT Plus",
                            matched_keywords=["chatgpt"],
                            listed_price=88.0,
                            product_status="有货",
                            product_url=f"https://pay.ldxp.cn/shop/{token}/item/P1",
                            content_hash=f"hash-{token}",
                        )
                    ],
                ),
                run_id,
            )
    finally:
        db.close()


def test_ldxp_opt_out_excludes_shop_from_sqlite_publication(tmp_path):
    crawler_db = tmp_path / "crawler.db"
    _seed_crawler_db(crawler_db)

    api_db_path = tmp_path / "api.db"
    database_url = f"sqlite:///{api_db_path.as_posix()}"
    engine = create_engine(database_url)
    ApiBase.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(SourcePolicyRequest(
            source_url="https://pay.ldxp.cn/shop/TEST01",
            request_type="opt_out",
            requester_email="owner@example.com",
            status="applied",
            temporary_hold_at=__import__("app.services.source_intake", fromlist=["utcnow"]).utcnow(),
            decided_at=__import__("app.services.source_intake", fromlist=["utcnow"]).utcnow(),
            decision_note="verified",
        ))
        db.commit()

    pipeline_db = session_for(database_url)
    try:
        result = publish_sources(
            pipeline_db,
            [SourceSpec("ldxp", str(crawler_db))],
            source_label="ldxp-opt-out-e2e",
        )
        assert result.offer_count == 1
        from common import Offer, Shop

        shops = list(pipeline_db.scalars(select(Shop).order_by(Shop.token)))
        assert [shop.token for shop in shops] == ["TEST02"]
        assert not any(shop.token == "TEST01" for shop in shops)
        offers = list(pipeline_db.scalars(select(Offer)))
        assert len(offers) == 1
    finally:
        pipeline_db.close()
