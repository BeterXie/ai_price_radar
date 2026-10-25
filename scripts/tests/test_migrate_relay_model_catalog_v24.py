import json

import pytest
from sqlalchemy import create_engine, inspect, text

from scripts.migrate_relay_model_catalog_v24 import migrate


def test_v24_adds_empty_cache_and_repeated_migration_preserves_model_data():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE relay_stations (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO relay_stations VALUES (1, 'Existing')"))
    migrate(engine)
    migrate(engine)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT name, model_catalog, groups, icon_cache FROM relay_stations")).one()
        assert row.name == "Existing" and json.loads(row.model_catalog) == {}
        assert json.loads(row.groups) == []
        assert json.loads(row.icon_cache) == {}
        conn.execute(text("UPDATE relay_stations SET model_catalog=:catalog"), {"catalog": '{"models":[{"id":"live-model"}]}'})
        conn.execute(text("UPDATE relay_stations SET groups=:groups"), {"groups": '[{"id":"vip","name":"VIP","ratio":0.5}]'})
        conn.execute(text("UPDATE relay_stations SET icon_cache=:cache"), {"cache": '{"marker":"preserved"}'})
    migrate(engine)
    with engine.connect() as conn:
        assert json.loads(conn.execute(text("SELECT model_catalog FROM relay_stations")).scalar_one())["models"][0]["id"] == "live-model"
        assert json.loads(conn.execute(text("SELECT groups FROM relay_stations")).scalar_one())[0]["ratio"] == .5
        assert json.loads(conn.execute(text("SELECT icon_cache FROM relay_stations")).scalar_one())["marker"] == "preserved"
    engine.dispose()


def test_v24_refuses_uninitialized_database():
    engine = create_engine("sqlite://")
    with pytest.raises(RuntimeError, match="run v22 first"):
        migrate(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()
