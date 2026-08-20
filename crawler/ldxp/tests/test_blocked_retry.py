from __future__ import annotations

from datetime import datetime, timezone

import ldxp_gpt_crawler as cli
from ldxp_crawler.db import StateDB
from ldxp_crawler.models import ProductMatch, ShopScanResult


def test_successful_scan_keeps_only_current_match_state(tmp_path):
    db = StateDB(tmp_path / "crawler.db")
    db.upsert_candidate("SHOP1", "https://pay.ldxp.cn/shop/SHOP1", "test", 100)
    db.save_scan_result(
        ShopScanResult(
            token="SHOP1",
            status="success",
            matches=[
                ProductMatch(
                    product_key="P1",
                    product_name="ChatGPT",
                    matched_keywords=["gpt"],
                )
            ],
        ),
        run_id=None,
    )

    tables = {
        row[0]
        for row in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert "product_snapshots" not in tables
    assert db.conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
    db.close()


def test_blocked_candidate_retries_after_backoff_and_manual_override(tmp_path):
    db = StateDB(tmp_path / "crawler.db")
    db.upsert_candidate("BLOCKED1", "https://pay.ldxp.cn/shop/BLOCKED1", "test", 100)
    db.save_scan_result(
        ShopScanResult(token="BLOCKED1", status="blocked", error="temporary block"),
        run_id=None,
    )

    row = db.conn.execute(
        "SELECT status, next_retry_at FROM candidates WHERE token=?",
        ("BLOCKED1",),
    ).fetchone()
    assert row["status"] == "blocked"
    assert datetime.fromisoformat(row["next_retry_at"]) > datetime.now(timezone.utc)
    assert db.list_candidates(rescan=True) == []

    db.conn.execute(
        "UPDATE candidates SET next_retry_at=? WHERE token=?",
        ("2000-01-01T00:00:00+00:00", "BLOCKED1"),
    )
    db.conn.commit()
    assert [row["token"] for row in db.list_candidates()] == ["BLOCKED1"]
    assert [row["token"] for row in db.list_candidates(rescan=True)] == ["BLOCKED1"]

    db.conn.execute(
        "UPDATE candidates SET next_retry_at=? WHERE token=?",
        ("2999-01-01T00:00:00+00:00", "BLOCKED1"),
    )
    db.conn.commit()
    assert [row["token"] for row in db.list_candidates(retry_blocked=True)] == ["BLOCKED1"]
    assert [row["token"] for row in db.list_candidates(rescan=True, retry_blocked=True)] == ["BLOCKED1"]
    db.close()


def test_all_blocked_batch_is_failed_and_circuit_breaks(tmp_path, monkeypatch):
    db_path = tmp_path / "crawler.db"
    db = StateDB(db_path)
    for index in range(5):
        token = f"BLOCKED{index}"
        db.upsert_candidate(token, f"https://pay.ldxp.cn/shop/{token}", "test", 100 - index)

    class BlockedScanner:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def scan_shop(self, candidate, _keywords):
            return ShopScanResult(
                token=candidate["token"],
                status="blocked",
                error="temporary block",
            )

    monkeypatch.setattr(cli, "BrowserShopScanner", BlockedScanner)
    args = cli.build_parser().parse_args(
        [
            "scan",
            "--db",
            str(db_path),
            "--rescan",
            "--retry-blocked",
            "--limit",
            "100",
            "--circuit-breaker",
            "3",
            "--manual-challenge-seconds",
            "0",
        ]
    )

    summary = cli.run_scan(args, db, cli.make_logger(False))
    assert summary == {
        "attempted": 3,
        "successful": 0,
        "failed": 3,
        "blocked": 3,
        "matches": 0,
        "circuit_broken": True,
    }
    latest = db.latest_run()
    assert latest["successful"] == 0
    assert latest["failed"] == 3
    assert latest["blocked"] == 3
    assert latest["circuit_broken"] == 1
    db.close()
