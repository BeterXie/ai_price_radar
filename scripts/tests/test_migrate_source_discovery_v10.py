from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg import sql

from scripts.migrate_source_intake_v8 import connection_url
from scripts.migrate_source_discovery_v10 import DDL, migrate


def test_source_discovery_v10_ddl_is_idempotent_and_constrained():
    assert DDL.count("CREATE TABLE IF NOT EXISTS") == 2
    assert "DROP CONSTRAINT IF EXISTS ck_source_candidates_status" in DDL
    assert "DROP CONSTRAINT IF EXISTS ck_source_candidates_platform" in DDL
    assert "DROP CONSTRAINT IF EXISTS uq_source_candidates_key" in DDL
    assert "REFERENCES source_intakes(id)" in DDL
    assert "REFERENCES source_discovery_runs(id)" in DDL
    assert "DROP TABLE" not in DDL


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_source_discovery_v10_runs_twice_on_postgres_16_and_preserves_intakes():
    schema = f"source_discovery_v10_{uuid.uuid4().hex}"
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
                        source_url TEXT NOT NULL,
                        detected_platform VARCHAR(30) NOT NULL DEFAULT 'unknown',
                        status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
                        contact_email VARCHAR(200) NOT NULL DEFAULT '',
                        shop_name TEXT NOT NULL DEFAULT '',
                        note TEXT NOT NULL DEFAULT '',
                        decision_note TEXT NOT NULL DEFAULT '',
                        failure_reason TEXT NOT NULL DEFAULT '',
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        product_count INTEGER NOT NULL DEFAULT 0,
                        declared_platform VARCHAR(30) NOT NULL DEFAULT 'auto',
                        origin VARCHAR(30) NOT NULL DEFAULT 'manual'
                    );
                    INSERT INTO source_intakes(source_type, source_key, source_url)
                    VALUES ('dujiao_next', 'https://kept.example', 'https://kept.example');
                    """
                )
                migrate(connection)
                migrate(connection)
                cursor.execute(
                    """
                    INSERT INTO source_discovery_runs(trigger, adapters, status)
                    VALUES ('manual', '["seed"]', 'succeeded');
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO source_candidates(
                        candidate_key, discovered_url, canonical_url,
                        detected_platform, status, promoted_intake_id, discovery_run_id
                    ) VALUES (
                        'sha256:abc', 'https://candidate.example/products/x',
                        'https://candidate.example/products/x',
                        'woocommerce', 'promoted',
                        (SELECT id FROM source_intakes WHERE source_key='https://kept.example'),
                        (SELECT id FROM source_discovery_runs LIMIT 1)
                    );
                    """
                )
                with pytest.raises(psycopg.errors.UniqueViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_candidates(
                                candidate_key, discovered_url, canonical_url, status
                            ) VALUES (
                                'sha256:abc', 'https://candidate.example/products/y',
                                'https://candidate.example/products/y', 'discovered'
                            )
                            """
                        )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_candidates(
                                candidate_key, discovered_url, canonical_url, status
                            ) VALUES (
                                'sha256:bad-status', 'https://bad.example', 'https://bad.example', 'not-a-status'
                            )
                            """
                        )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_candidates(
                                candidate_key, discovered_url, canonical_url,
                                detected_platform, status
                            ) VALUES (
                                'sha256:bad-platform', 'https://bad.example', 'https://bad.example',
                                'shopify', 'discovered'
                            )
                            """
                        )
                with pytest.raises(psycopg.errors.ForeignKeyViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_candidates(
                                candidate_key, discovered_url, canonical_url,
                                detected_platform, status, promoted_intake_id
                            ) VALUES (
                                'sha256:bad-fk', 'https://bad.example', 'https://bad.example',
                                'schema_org', 'discovered', 999999
                            )
                            """
                        )
                cursor.execute(
                    "SELECT source_key, source_type FROM source_intakes WHERE source_key='https://kept.example'"
                )
                assert cursor.fetchone() == ("https://kept.example", "dujiao_next")
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()
