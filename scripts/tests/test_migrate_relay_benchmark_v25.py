import pytest
from sqlalchemy import create_engine, text

from scripts.migrate_relay_benchmark_v25 import migrate


def test_repeatable_migration_preserves_legacy_and_benchmark_data():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE relay_probe_results (id INTEGER PRIMARY KEY, input_tokens INTEGER, cached_input_tokens INTEGER)"))
        connection.execute(text("INSERT INTO relay_probe_results VALUES (1, 8, 0)"))
    migrate(engine)
    migrate(engine)
    with engine.begin() as connection:
        assert tuple(connection.execute(text("SELECT input_tokens, cached_input_tokens, benchmark_version, candy_verdict, candy_answer, cache_probe_status FROM relay_probe_results")).one()) == (8, 0, None, None, None, None)
        connection.execute(text("UPDATE relay_probe_results SET benchmark_version='candy-cache-v1', candy_verdict='failed', candy_answer='31', cache_probe_status='usage_missing'"))
    migrate(engine)
    with engine.connect() as connection:
        assert tuple(connection.execute(text("SELECT benchmark_version, candy_verdict, candy_answer, cache_probe_status FROM relay_probe_results")).one()) == ("candy-cache-v1", "failed", "31", "usage_missing")


def test_requires_existing_metrics_schema():
    with pytest.raises(RuntimeError, match="run v23 first"):
        migrate(create_engine("sqlite://"))
