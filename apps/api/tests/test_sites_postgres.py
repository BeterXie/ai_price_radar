"""Run only against a disposable PostgreSQL database dedicated to this migration."""
import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.getenv("SITE_TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured")
def test_site_migration_twice_preserves_shared_catalog():
    url = os.environ["SITE_TEST_DATABASE_URL"]
    assert make_url(url).database == "brand_migration_test", "Use a dedicated disposable database"
    engine = create_engine(url)
    migration_path = Path(__file__).resolve().parents[3] / "scripts" / "migrate_multi_brand_v26.py"
    spec = importlib.util.spec_from_file_location("multi_brand_postgres_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as connection:
            assert inspect(connection).get_table_names() == [], "Rehearsal must start with an empty database"
            connection.execute(text("CREATE TABLE relay_stations (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, slug TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO products VALUES (42, 'existing-product')"))
        module.migrate(engine)
        module.migrate(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT slug FROM products WHERE id=42")).scalar_one() == "existing-product"
            assert set(inspect(connection).get_table_names()) == {
                "relay_stations", "products", "site_articles", "site_ads", "site_relays"
            }
            published = next(c for c in inspect(connection).get_columns("site_articles") if c["name"] == "published_at")
            assert published["type"].timezone is True
            assert connection.execute(text("SELECT count(*) FROM site_articles")).scalar_one() == 0
    finally:
        engine.dispose()
