import os
import uuid

import psycopg
import pytest
from psycopg import sql

from scripts.migrate_source_intake_v8 import DDL, connection_url, migrate


def test_source_intake_v8_migration_is_idempotent_and_preserves_legacy_states():
    assert "ADD COLUMN IF NOT EXISTS declared_platform" in DDL
    assert "ADD COLUMN IF NOT EXISTS detected_platform" in DDL
    assert "CREATE INDEX IF NOT EXISTS ix_source_intakes_declared_platform" in DDL
    assert "DROP CONSTRAINT IF EXISTS ck_source_intakes_type" in DDL
    assert "source_type='merchant_json'" in DDL
    assert "'unknown', 'ldxp', 'merchant_json', 'dujiao_next', 'other'" in DDL
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
                        report_id BIGINT UNIQUE,
                        source_type VARCHAR(30) NOT NULL,
                        source_key VARCHAR(300) NOT NULL,
                        source_url TEXT NOT NULL,
                        shop_name TEXT NOT NULL DEFAULT '',
                        contact_email VARCHAR(200) NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        origin VARCHAR(30) NOT NULL DEFAULT 'manual',
                        status VARCHAR(30) NOT NULL,
                        decision_note TEXT NOT NULL DEFAULT '',
                        failure_reason TEXT NOT NULL DEFAULT '',
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        product_count INTEGER NOT NULL DEFAULT 0,
                        lease_expires_at TIMESTAMPTZ,
                        approved_at TIMESTAMPTZ,
                        started_at TIMESTAMPTZ,
                        finished_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE(source_type, source_key)
                    );
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
                        CHECK (source_type IN ('ldxp', 'merchant_feed'));
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status
                        CHECK (status IN ('pending_review', 'queued', 'onboarded'));
                    INSERT INTO source_intakes(
                        source_type, source_key, source_url, contact_email, note,
                        status, attempt_count, created_at, updated_at
                    ) VALUES
                        ('merchant_feed', 'https://feed.example/catalog.json', 'https://feed.example/catalog.json',
                         'legacy@example.com', 'legacy note', 'queued', 1, now() - interval '2 days', now() - interval '1 day'),
                        ('merchant_json', 'https://feed.example/catalog.json', 'https://feed.example/catalog.json',
                         'current@example.com', 'current note', 'published', 2, now() - interval '1 day', now());
                    """
                )
                assert migrate(connection) == 1
                assert migrate(connection) == 0
                cursor.execute(
                    "SELECT source_type, declared_platform, detected_platform, status, contact_email, note, attempt_count "
                    "FROM source_intakes WHERE source_key='https://feed.example/catalog.json'"
                )
                source_type, declared, detected, status, contact, note, attempts = cursor.fetchone()
                assert (source_type, detected, status, contact, attempts) == (
                    "merchant_json", "merchant_json", "published", "current@example.com", 3
                )
                assert declared in {"auto", "merchant_json"}
                assert "legacy note" in note and "current note" in note
                cursor.execute(
                    "INSERT INTO source_intakes(source_type, source_key, source_url, contact_email, status) "
                    "VALUES ('dujiao_next', 'approved-shop', 'https://approved.example', "
                    "'owner@example.com', 'needs_re_review')"
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
