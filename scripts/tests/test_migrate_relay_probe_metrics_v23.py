import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from scripts.migrate_relay_probe_metrics_v23 import migrate


def legacy_samples(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE relay_probe_results (id INTEGER PRIMARY KEY, station_id INTEGER, revision INTEGER, checked_at TIMESTAMP, status TEXT, latency_ms INTEGER, http_status INTEGER)"))
        connection.execute(text("INSERT INTO relay_probe_results VALUES (1, 2, 3, CURRENT_TIMESTAMP, 'healthy', 345, 200)"))


def test_v23_is_repeatable_and_keeps_old_metrics_unknown():
    engine = create_engine("sqlite://")
    legacy_samples(engine)
    migrate(engine)
    migrate(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT latency_ms, connect_latency_ms, first_token_ms, input_tokens, cached_input_tokens FROM relay_probe_results")).one()
        assert tuple(row) == (345, None, None, None, None)
        connection.execute(text("UPDATE relay_probe_results SET connect_latency_ms=20, first_token_ms=100, input_tokens=1000, cached_input_tokens=900"))
        connection.commit()
    migrate(engine)
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT connect_latency_ms, first_token_ms, input_tokens, cached_input_tokens FROM relay_probe_results")).one()) == (20, 100, 1000, 900)
    engine.dispose()


def test_v23_refuses_an_uninitialized_database():
    engine = create_engine("sqlite://")
    with pytest.raises(RuntimeError, match="run v22 first"):
        migrate(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_v23_cli_does_not_load_application_dotenv(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    legacy_samples(engine)
    engine.dispose()
    (tmp_path / ".env").write_bytes(b"\xff")
    script = Path(__file__).resolve().parents[1] / "migrate_relay_probe_metrics_v23.py"
    result = subprocess.run([sys.executable, str(script), "--database-url", url], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
