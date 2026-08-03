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
    assert "declared_platform='merchant_json'" in DDL
    assert "detected_platform='merchant_json'" in DDL
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
                        report_id, source_type, source_key, source_url, shop_name,
                        contact_email, note, origin, status, decision_note,
                        failure_reason, attempt_count, product_count,
                        lease_expires_at, approved_at, started_at, finished_at,
                        created_at, updated_at
                    ) VALUES
                        (101, 'merchant_feed', 'https://feed.example/catalog.json', 'https://legacy.example/catalog.json',
                         'Legacy Shop', 'legacy@example.com', 'legacy note', 'manual', 'onboarded', 'legacy decision',
                         'legacy failure', 1, 9, '2026-01-05 00:00:00+00', '2026-01-02 00:00:00+00',
                         '2026-01-03 00:00:00+00', '2026-01-04 00:00:00+00',
                         '2026-01-01 00:00:00+00', '2026-01-05 00:00:00+00');

                    ALTER TABLE source_intakes DROP CONSTRAINT ck_source_intakes_type;
                    ALTER TABLE source_intakes DROP CONSTRAINT ck_source_intakes_status;
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
                        CHECK (source_type IN ('ldxp', 'merchant_feed', 'merchant_json'));
                    ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_status
                        CHECK (status IN ('pending_review', 'queued', 'onboarded', 'published'));
                    ALTER TABLE source_intakes ADD COLUMN declared_platform VARCHAR(30);
                    ALTER TABLE source_intakes ADD COLUMN detected_platform VARCHAR(30);
                    UPDATE source_intakes
                    SET declared_platform='merchant_feed', detected_platform='merchant_feed';
                    INSERT INTO source_intakes(
                        source_type, declared_platform, detected_platform, source_key, source_url, shop_name,
                        contact_email, note, origin, status, decision_note,
                        failure_reason, attempt_count, product_count,
                        lease_expires_at, approved_at, started_at, finished_at,
                        created_at, updated_at
                    ) VALUES
                        ('merchant_json', 'merchant_json', 'merchant_json', 'https://feed.example/catalog.json',
                         'https://current.example/catalog.json',
                         '', 'current@example.com', 'current note', 'discovered', 'published', 'current decision',
                         'current failure', 2, 4, '2026-02-05 00:00:00+00', '2026-02-02 00:00:00+00',
                         '2026-02-03 00:00:00+00', '2026-02-04 00:00:00+00',
                         '2026-02-01 00:00:00+00', '2026-02-05 00:00:00+00');
                    """
                )
                connection.commit()

                assert migrate(connection) == 1
                cursor.execute(
                    "SELECT report_id, source_type, declared_platform, detected_platform, source_url, shop_name, "
                    "contact_email, note, origin, status, decision_note, failure_reason, attempt_count, product_count, "
                    "lease_expires_at, approved_at, started_at, finished_at, created_at, updated_at "
                    "FROM source_intakes WHERE source_key='https://feed.example/catalog.json'"
                )
                first_snapshot = cursor.fetchone()
                assert first_snapshot[:14] == (
                    101,
                    "merchant_json",
                    "merchant_json",
                    "merchant_json",
                    "https://current.example/catalog.json",
                    "Legacy Shop",
                    "current@example.com",
                    "current note\nlegacy note",
                    "manual",
                    "published",
                    "current decision\nlegacy decision",
                    "current failure\nlegacy failure",
                    3,
                    9,
                )
                assert [value.isoformat() for value in first_snapshot[14:]] == [
                    "2026-02-05T00:00:00+00:00",
                    "2026-01-02T00:00:00+00:00",
                    "2026-01-03T00:00:00+00:00",
                    "2026-02-04T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    "2026-02-05T00:00:00+00:00",
                ]
                cursor.execute(
                    "SELECT count(*) FROM source_intakes "
                    "WHERE source_key='https://feed.example/catalog.json'"
                )
                assert cursor.fetchone()[0] == 1

                cursor.execute(
                    "INSERT INTO source_intakes(source_type, source_key, source_url, contact_email, status) VALUES "
                    "('unknown', 'new-submission', 'https://submitted.example', 'new@example.com', 'submitted'), "
                    "('dujiao_next', 'approved-shop', 'https://approved.example', 'owner@example.com', 'needs_re_review')"
                )
                assert migrate(connection) == 0
                cursor.execute(
                    "SELECT report_id, source_type, declared_platform, detected_platform, source_url, shop_name, "
                    "contact_email, note, origin, status, decision_note, failure_reason, attempt_count, product_count, "
                    "lease_expires_at, approved_at, started_at, finished_at, created_at, updated_at "
                    "FROM source_intakes WHERE source_key='https://feed.example/catalog.json'"
                )
                assert cursor.fetchone() == first_snapshot

                cursor.execute(
                    "SELECT column_default, is_nullable FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name='source_intakes' AND column_name='declared_platform'",
                    (schema,),
                )
                default, nullable = cursor.fetchone()
                assert "auto" in default
                assert nullable == "NO"
                cursor.execute(
                    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid='source_intakes'::regclass "
                    "AND conname IN ('ck_source_intakes_type', 'ck_source_intakes_status') "
                    "ORDER BY conname"
                )
                constraints = dict(cursor.fetchall())
                assert "unknown" in constraints["ck_source_intakes_type"]
                assert "merchant_feed" not in constraints["ck_source_intakes_type"]
                assert "submitted" in constraints["ck_source_intakes_status"]
                assert "published" in constraints["ck_source_intakes_status"]
                cursor.execute(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid='source_intakes'::regclass AND contype='u' "
                    "AND pg_get_constraintdef(oid)='UNIQUE (source_type, source_key)'"
                )
                assert cursor.fetchone()[0] == 1
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()
