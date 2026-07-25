import sqlite3

import sync_ldxp


def test_load_records_opens_source_read_only(tmp_path, monkeypatch):
    source = tmp_path / "crawler.db"
    conn = sqlite3.connect(source)
    conn.executescript(
        """
        CREATE TABLE candidates (
            token TEXT PRIMARY KEY,
            status TEXT,
            source_score INTEGER,
            last_success_at TEXT,
            scanned_at TEXT
        );
        CREATE TABLE matches (
            token TEXT,
            product_name TEXT,
            collected_at TEXT
        );
        INSERT INTO candidates VALUES ('shop', 'success', 1, NULL, NULL);
        INSERT INTO matches VALUES ('shop', 'GPT Plus', '2026-07-26T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    original_connect = sqlite3.connect
    captured = {}

    def capture_connect(database, *args, **kwargs):
        captured["database"] = database
        captured["uri"] = kwargs.get("uri")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sync_ldxp.sqlite3, "connect", capture_connect)

    records = list(sync_ldxp.load_records(source))

    assert records[0]["product_name"] == "GPT Plus"
    assert captured["database"].endswith("?mode=ro")
    assert captured["uri"] is True
