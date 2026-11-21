from sqlalchemy import create_engine, inspect, text
from scripts.migrate_collectors_v28 import migrate


def test_collector_migration_is_repeatable_and_preserves_work():
    engine = create_engine('sqlite://')
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO collector_jobs(id,kind,active_lane,release) VALUES ('job','scan','catalog','test')"))
    migrate(engine)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT status FROM collector_jobs')).scalar() == 'queued'
    assert 'lease_token' in {c['name'] for c in inspect(engine).get_columns('collector_jobs')}
    engine.dispose()
