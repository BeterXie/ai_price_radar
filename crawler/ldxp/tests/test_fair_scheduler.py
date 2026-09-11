from __future__ import annotations

from ldxp_crawler.db import StateDB
from ldxp_crawler.models import ProductMatch, ShopScanResult


def test_fair_scheduler_prevents_low_score_shop_starvation(tmp_path):
    db = StateDB(tmp_path / "test_fair.db")
    # Shop A: high score, recently attempted
    db.upsert_candidate("SHOP_A", "https://pay.ldxp.cn/shop/SHOP_A", "intake", 1_000_000)
    db.save_scan_result(
        ShopScanResult(
            token="SHOP_A",
            status="success",
            matches=[ProductMatch(product_key="P_A", product_name="ChatGPT Plus A", matched_keywords=["gpt"])],
        ),
        run_id=None,
    )
    db.conn.execute("UPDATE candidates SET last_attempt_at='2026-09-11T06:50:00+00:00' WHERE token='SHOP_A'")

    # Shop B: low score, attempted 2 hours ago
    db.upsert_candidate("SHOP_B", "https://pay.ldxp.cn/shop/SHOP_B", "wayback", 10)
    db.save_scan_result(
        ShopScanResult(
            token="SHOP_B",
            status="success",
            matches=[ProductMatch(product_key="P_B", product_name="ChatGPT Plus B", matched_keywords=["gpt"])],
        ),
        run_id=None,
    )
    db.conn.execute("UPDATE candidates SET last_attempt_at='2026-09-11T04:50:00+00:00' WHERE token='SHOP_B'")

    # Shop C: matched shop, never attempted
    db.upsert_candidate("SHOP_C", "https://pay.ldxp.cn/shop/SHOP_C", "seed", 50)
    db.conn.execute(
        "INSERT INTO matches(token, product_name, matched_keywords, collected_at) VALUES ('SHOP_C', 'ChatGPT C', '[\"gpt\"]', '2026-09-11T00:00:00+00:00')"
    )
    db.conn.commit()

    # Query with matched_only=True and rescan=True (inventory scan)
    ordered = [row["token"] for row in db.list_candidates(rescan=True, matched_only=True)]
    # Shop C (unattempted) comes first, then Shop B (oldest attempt: 04:50), then Shop A (recent attempt: 06:50)
    assert ordered == ["SHOP_C", "SHOP_B", "SHOP_A"], f"Expected ['SHOP_C', 'SHOP_B', 'SHOP_A'], got {ordered}"

    # Intake pending shop should jump to the front
    db.upsert_intake_candidate(
        intake_id=999,
        token="SHOP_INTAKE",
        url="https://pay.ldxp.cn/shop/SHOP_INTAKE",
        shop_name="Intake Shop",
        attempt_count=1,
    )
    ordered_with_intake = [row["token"] for row in db.list_candidates(rescan=True, matched_only=True)]
    assert ordered_with_intake[0] == "SHOP_INTAKE"
    db.close()
