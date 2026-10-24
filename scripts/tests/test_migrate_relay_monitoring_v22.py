import pytest
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

from scripts.migrate_relay_monitoring_v22 import migrate


def test_v22_preserves_legacy_relays_and_is_repeatable():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE relay_stations (id INTEGER PRIMARY KEY, name TEXT, is_enabled BOOLEAN)"))
        connection.execute(text("INSERT INTO relay_stations VALUES (1, 'Legacy', TRUE)"))
    migrate(engine)
    migrate(engine)
    with engine.begin() as connection:
        row = connection.execute(text("SELECT name, is_enabled, review_status, monitor_enabled, encrypted_api_key FROM relay_stations")).one()
        assert tuple(row) == ("Legacy", True, "approved", False, "")
        assert "relay_probe_results" in inspect(connection).get_table_names()
        connection.execute(text("INSERT INTO relay_probe_results (station_id, revision, checked_at, status, latency_ms) VALUES (1, 1, CURRENT_TIMESTAMP, 'healthy', 10)"))
    engine.dispose()


def test_v22_refuses_an_uninitialized_database():
    engine = create_engine("sqlite://")
    with pytest.raises(RuntimeError, match="requires existing"):
        migrate(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_v22_cli_uses_explicit_database_without_reading_application_dotenv(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE relay_stations (id INTEGER PRIMARY KEY, name TEXT)"))
    engine.dispose()
    # An application settings import would attempt UTF-8 decoding of this file.
    # Migrations must rely solely on the database URL provided by the operator.
    (tmp_path / ".env").write_bytes(b"\xff")
    script = Path(__file__).resolve().parents[1] / "migrate_relay_monitoring_v22.py"
    result = subprocess.run([sys.executable, str(script), "--database-url", database_url], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
