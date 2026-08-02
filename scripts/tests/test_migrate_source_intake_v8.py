import os
import uuid

import psycopg
import pytest
from psycopg import sql

from scripts.migrate_source_intake_v8 import DDL, connection_url


def test_source_intake_v8_migration_is_idempotent_and_preserves_legacy_states():
    assert "ADD COLUMN IF NOT EXISTS declared_platform" in DDL
    assert "ADD COLUMN IF NOT EXISTS detected_platform" in DDL
    assert "CREATE INDEX IF NOT EXISTS ix_source_intakes_declared_platform" in DDL
    assert "DROP CONSTRAINT IF EXISTS ck_source_intakes_type" in DDL
    assert "'merchant_feed', 'merchant_json', 'dujiao_next', 'other'" in DDL
    assert "'approved', 'syncing', 'published'" in DDL
    assert "'queued', 'validating', 'validated', 'onboarded'" in DDL
    assert "WHERE declared_platform IS NULL" in DDL
    assert "WHERE detected_platform IS NULL" in DDL
    assert connection_url("postgresql+psycopg://user:pass@db/app") == "postgresql://user:pass@db/app"


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_source_intake_v8_migration_runs_twice_on_postgresql():
    schema = f"intake_v8_{uuid.uuid4().hex}"
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
                        status VARCHAR(30) NOT NULL
                    );
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
                        CHECK (source_type IN ('ldxp', 'merchant_feed'));
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status
                        CHECK (status IN ('pending_review', 'queued', 'onboarded'));
                    INSERT INTO source_intakes(source_type, source_key, status)
                    VALUES ('merchant_feed', 'legacy-feed', 'queued');
                    """
                )
                cursor.execute(DDL)
                cursor.execute(DDL)
                cursor.execute(
                    "SELECT declared_platform, detected_platform FROM source_intakes WHERE source_key='legacy-feed'"
                )
                assert cursor.fetchone() == ("merchant_json", "merchant_json")
                cursor.execute(
                    "INSERT INTO source_intakes(source_type, source_key, status) "
                    "VALUES ('dujiao_next', 'approved-shop', 'needs_re_review')"
                )
                cursor.execute(
                    "SELECT column_default, is_nullable FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name='source_intakes' AND column_name='declared_platform'",
                    (schema,),
                )
                default, nullable = cursor.fetchone()
                assert "auto" in default
                assert nullable == "NO"
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()
