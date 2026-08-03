import os
import uuid

import psycopg
import pytest
from psycopg import sql

from scripts.migrate_source_intake_v8 import connection_url
from scripts.migrate_source_platforms_v9 import DDL, migrate


def test_source_platform_v9_expands_only_the_persisted_source_types():
    assert "DROP CONSTRAINT IF EXISTS ck_source_intakes_type" in DDL
    assert "'woocommerce', 'schema_org'" in DDL
    assert "merchant_feed" not in DDL


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_source_platform_v9_runs_twice_and_accepts_new_platforms():
    schema = f"source_platform_v9_{uuid.uuid4().hex}"
    with psycopg.connect(connection_url(os.environ["TEST_POSTGRES_URL"])) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                cursor.execute(
                    """
                    CREATE TABLE source_intakes (
                        id BIGSERIAL PRIMARY KEY,
                        source_type VARCHAR(30) NOT NULL,
                        source_key VARCHAR(300) NOT NULL,
                        source_url TEXT NOT NULL
                    );
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type CHECK (
                        source_type IN ('unknown', 'ldxp', 'merchant_json', 'dujiao_next', 'other')
                    );
                    """
                )
                migrate(connection)
                migrate(connection)
                cursor.execute(
                    "INSERT INTO source_intakes(source_type, source_key, source_url) VALUES "
                    "('woocommerce', 'https://woo.example', 'https://woo.example'), "
                    "('schema_org', 'https://structured.example', 'https://structured.example')"
                )
                cursor.execute("SELECT source_type FROM source_intakes ORDER BY source_type")
                assert [row[0] for row in cursor.fetchall()] == ["schema_org", "woocommerce"]
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()
