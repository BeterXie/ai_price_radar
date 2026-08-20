import sqlite3
from pathlib import Path

from scripts.build_crawler_publish_db import build_publish_db


def test_build_publish_db_supports_production_python_syntax():
    source = (Path(__file__).resolve().parents[1] / "build_crawler_publish_db.py").read_text(encoding="utf-8")
    assert "dict[" not in source
    assert "missing_ok=" not in source


def test_build_publish_db_copies_only_current_publisher_inputs(tmp_path):
    source = tmp_path / "crawler.db"
    target = tmp_path / "publish.db"
    db = sqlite3.connect(source)
    db.executescript(
        """
        CREATE TABLE candidates (token TEXT PRIMARY KEY, status TEXT NOT NULL);
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            collected_at TEXT NOT NULL
        );
        CREATE TABLE dujiao_candidates (
            origin TEXT PRIMARY KEY,
            review_status TEXT NOT NULL
        );
        CREATE TABLE product_snapshots (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        INSERT INTO candidates VALUES ('shop', 'success');
        INSERT INTO matches(token, collected_at) VALUES ('shop', '2026-08-20T00:00:00Z');
        INSERT INTO dujiao_candidates VALUES ('https://shop.example', 'approved');
        INSERT INTO product_snapshots(payload) VALUES (printf('%.*c', 1000000, 'x'));
        """
    )
    db.commit()
    db.close()
    source.chmod(0o444)

    counts = build_publish_db(source, target)

    assert counts == {"candidates": 1, "matches": 1, "dujiao_candidates": 1}
    published = sqlite3.connect(target)
    tables = {
        row[0]
        for row in published.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == {"candidates", "matches", "dujiao_candidates"}
    assert published.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    published.close()
    assert target.stat().st_size < source.stat().st_size
