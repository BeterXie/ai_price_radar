from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler" / "ldxp"))

from ldxp_crawler.db import StateDB  # noqa: E402
from ldxp_crawler.models import ProductMatch, ShopScanResult  # noqa: E402
from scripts.purge_ldxp_raw_v11 import _sqlite_counts, _sqlite_purge  # noqa: E402
from scripts.purge_ldxp_raw_v11 import main as purge_main  # noqa: E402


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


def test_purge_apply_aborts_before_destructive_steps_without_pg_backup(tmp_path, monkeypatch):
    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    state_file = crawler_dir / "browser_state.json"
    state_file.write_text("{}", encoding="utf-8")
    profile = crawler_dir / "browser_profile"
    profile.mkdir()
    (profile / "Default").mkdir()
    (profile / "Default" / "Preferences").write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "purge_ldxp_raw_v11.py",
            "--apply",
            "--crawler-db", str(db_path),
            "--crawler-dir", str(crawler_dir),
            "--database-url", "postgresql+psycopg://user:pass@127.0.0.1:5432/db",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        purge_main()
    assert exc.value.code == 2
    assert _sqlite_counts(db_path)["matches_raw_json"] == 1  # unchanged
    assert state_file.exists()
    assert (profile / "Default" / "Preferences").exists()


def test_purge_apply_aborts_when_postgres_connection_fails(tmp_path, monkeypatch):
    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    state_file = crawler_dir / "browser_state.json"
    state_file.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "purge_ldxp_raw_v11.py",
            "--apply",
            "--skip-postgres-backup-check",
            "--crawler-db", str(db_path),
            "--crawler-dir", str(crawler_dir),
            "--database-url", "postgresql+psycopg://user:pass@127.0.0.1:1/db",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        purge_main()
    assert exc.value.code == 2
    assert _sqlite_counts(db_path)["matches_raw_json"] == 1  # unchanged
    assert state_file.exists()


def test_purge_apply_rolls_back_sqlite_when_postgres_fails_midway(tmp_path, monkeypatch):
    import scripts.purge_ldxp_raw_v11 as purge_module

    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    state_file = crawler_dir / "browser_state.json"
    state_file.write_text("{}", encoding="utf-8")

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, *_args, **_kwargs):
            return None

        def fetchone(self):
            return (0,)

    class FakeConn:
        def __init__(self):
            self.rolled_back = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

        def rollback(self):
            self.rolled_back = True

        def close(self):
            return None

    def broken_purge(*_args, **_kwargs):
        raise RuntimeError("postgres update failed")

    fake_conn = FakeConn()
    monkeypatch.setattr(purge_module.psycopg, "connect", lambda _url: fake_conn)
    monkeypatch.setattr(purge_module, "_postgres_counts", lambda _conn: {"postgres_ldxp_raw_json": 0})
    monkeypatch.setattr(purge_module, "_postgres_purge", broken_purge)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "purge_ldxp_raw_v11.py",
            "--apply",
            "--skip-postgres-backup-check",
            "--crawler-db", str(db_path),
            "--crawler-dir", str(crawler_dir),
            "--database-url", "postgresql+psycopg://user:pass@db/db",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        purge_main()
    assert exc.value.code == 2
    assert _sqlite_counts(db_path)["matches_raw_json"] == 1  # restored from backup
    assert state_file.exists()
    assert fake_conn.rolled_back is True
