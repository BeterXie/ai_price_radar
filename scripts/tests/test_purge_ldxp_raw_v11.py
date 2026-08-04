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
    assert purge_main() == 2
    assert _sqlite_counts(db_path)["matches_raw_json"] == 1  # restored from backup
    assert state_file.exists()
    assert fake_conn.rolled_back is True


def test_postgres_empty_json_is_not_counted_as_raw():
    import scripts.purge_ldxp_raw_v11 as purge_module

    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, sql, *_args):
            captured["sql"] = sql
            return None

        def fetchone(self):
            return (0,)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    result = purge_module._postgres_counts(FakeConn())  # type: ignore[arg-type]
    assert result == {"postgres_ldxp_nonempty_raw_json": 0}
    assert "raw_json <> '{}'::jsonb" in captured["sql"]


def _fake_pg_connection(monkeypatch, *, commit_raises=False):
    import scripts.purge_ldxp_raw_v11 as purge_module

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
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()
            return None

        def cursor(self):
            return FakeCursor()

        def commit(self):
            if commit_raises:
                raise RuntimeError("commit failed")
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    conn = FakeConn()
    monkeypatch.setattr(purge_module.psycopg, "connect", lambda _url: conn)
    monkeypatch.setattr(purge_module, "_postgres_counts", lambda _conn: {"postgres_ldxp_nonempty_raw_json": 0})
    return conn


def _seed_artifact_files(crawler_dir: Path) -> Path:
    state_file = crawler_dir / "browser_state.json"
    state_file.write_text("{}", encoding="utf-8")
    return state_file


def test_apply_summary_contains_postgres_before_and_after(tmp_path, monkeypatch):
    import scripts.purge_ldxp_raw_v11 as purge_module

    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    _seed_artifact_files(crawler_dir)
    conn = _fake_pg_connection(monkeypatch)
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
    import json as json_module

    captured = {}
    original_print = print

    def fake_print(*args, **kwargs):
        captured["summary"] = json_module.loads(args[0])
        original_print(*args, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    assert purge_main() == 0
    summary = captured["summary"]
    assert summary["database_cleanup"] == "success"
    assert summary["postgres"] == {"postgres_ldxp_nonempty_raw_json": 0}
    assert summary["postgres_after"] == {"postgres_ldxp_nonempty_raw_json": 0}
    assert summary["sqlite_after"] == {"matches_raw_json": 0, "snapshot_raw_json": 0}
    assert conn.committed is True


def test_artifact_failure_after_db_commit_does_not_restore_databases(tmp_path, monkeypatch):
    import scripts.purge_ldxp_raw_v11 as purge_module

    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    _seed_artifact_files(crawler_dir)
    conn = _fake_pg_connection(monkeypatch)

    def broken_remove(path):
        raise PermissionError("cannot remove")

    monkeypatch.setattr(purge_module, "_remove_tree", broken_remove)
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
    import json as json_module

    captured = {}
    original_print = print

    def fake_print(*args, **kwargs):
        captured["summary"] = json_module.loads(args[0])
        original_print(*args, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    assert purge_main() == 3
    summary = captured["summary"]
    assert summary["database_cleanup"] == "success"
    assert summary["artifact_cleanup"] == "partial"
    assert _sqlite_counts(db_path) == {"matches_raw_json": 0, "snapshot_raw_json": 0}
    assert conn.rolled_back is False


def test_pg_commit_failure_restores_sqlite_and_preserves_artifacts(tmp_path, monkeypatch):
    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    state_file = _seed_artifact_files(crawler_dir)
    conn = _fake_pg_connection(monkeypatch, commit_raises=True)
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
    assert purge_main() == 2
    assert _sqlite_counts(db_path)["matches_raw_json"] == 1  # restored
    assert state_file.exists()  # artifacts preserved
    assert conn.rolled_back is True


def test_second_dry_run_reports_zero_nonempty_raw(tmp_path, monkeypatch):
    import scripts.purge_ldxp_raw_v11 as purge_module

    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    _sqlite_purge(db_path, dry_run=False, backup=True)
    conn = _fake_pg_connection(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "purge_ldxp_raw_v11.py",
            "--dry-run",
            "--crawler-db", str(db_path),
            "--crawler-dir", str(crawler_dir),
            "--database-url", "postgresql+psycopg://user:pass@db/db",
        ],
    )
    import json as json_module

    captured = {}
    original_print = print

    def fake_print(*args, **kwargs):
        captured["summary"] = json_module.loads(args[0])
        original_print(*args, **kwargs)

    monkeypatch.setattr("builtins.print", fake_print)
    assert purge_main() == 0
    summary = captured["summary"]
    assert summary["sqlite"] == {"matches_raw_json": 0, "snapshot_raw_json": 0}
    assert summary["postgres"] == {"postgres_ldxp_nonempty_raw_json": 0}


def test_full_gzip_validation_detects_truncated_tail(tmp_path, monkeypatch):
    import gzip as gzip_module

    backups = tmp_path / "backups"
    backups.mkdir()
    full = gzip_module.compress(b"x" * 10000)
    target = backups / "price_radar_truncated.sql.gz"
    target.write_bytes(full[: len(full) // 2])
    crawler_dir = tmp_path / "data" / "crawler"
    crawler_dir.mkdir(parents=True)
    db_path = crawler_dir / "ldxp_crawler.db"
    _seed_db(db_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "purge_ldxp_raw_v11.py",
            "--apply",
            "--crawler-db", str(db_path),
            "--crawler-dir", str(crawler_dir),
            "--database-url", "postgresql+psycopg://user:pass@db/db",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        purge_main()
    assert exc.value.code == 2
