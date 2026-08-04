from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg import sql

from scripts.migrate_ldxp_policy_v11 import DDL, migrate
from scripts.migrate_source_intake_v8 import connection_url


def test_source_policy_v11_ddl_is_idempotent_and_constrained():
    assert DDL.count("CREATE TABLE IF NOT EXISTS") == 3
    assert "ck_source_policy_requests_type" in DDL
    assert "ck_source_policy_requests_status" in DDL
    assert "source_policy_effects" in DDL


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_source_policy_v11_runs_twice_and_enforces_constraints():
    schema = f"source_policy_v11_{uuid.uuid4().hex}"
    with psycopg.connect(connection_url(os.environ["TEST_POSTGRES_URL"])) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                migrate(connection)
                migrate(connection)
                cursor.execute(
                    """
                    INSERT INTO source_policy_requests(source_url, request_type, requester_email)
                    VALUES ('https://pay.ldxp.cn/shop/TEST01', 'opt_out', 'owner@example.com')
                    """
                )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_policy_requests(source_url, request_type, requester_email)
                            VALUES ('https://pay.ldxp.cn/shop/TEST02', 'invalid', 'owner@example.com')
                            """
                        )
                with pytest.raises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        cursor.execute(
                            """
                            INSERT INTO source_policy_requests(source_url, request_type, requester_email, status)
                            VALUES ('https://pay.ldxp.cn/shop/TEST03', 'opt_out', 'owner@example.com', 'bad')
                            """
                        )
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_source_policy_v11_upgrades_legacy_effects_table():
    schema = f"source_policy_v11_legacy_{uuid.uuid4().hex}"
    with psycopg.connect(connection_url(os.environ["TEST_POSTGRES_URL"])) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                cursor.execute(
                    """
                    CREATE TABLE source_policy_requests (
                        id BIGSERIAL PRIMARY KEY,
                        source_url TEXT NOT NULL,
                        request_type VARCHAR(20) NOT NULL,
                        requester_email VARCHAR(200) NOT NULL,
                        reason TEXT NOT NULL DEFAULT '',
                        status VARCHAR(20) NOT NULL,
                        temporary_hold_at TIMESTAMPTZ,
                        decided_at TIMESTAMPTZ,
                        decision_note TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    CREATE TABLE source_policy_effects (
                        id BIGSERIAL PRIMARY KEY,
                        policy_request_id BIGINT NOT NULL,
                        intake_id BIGINT NOT NULL,
                        previous_status VARCHAR(30) NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        reversed_at TIMESTAMPTZ
                    );
                    """
                )
                migrate(connection)
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'source_policy_effects'
                      AND column_name IN ('previous_finished_at', 'reverse_result')
                    ORDER BY column_name
                    """
                )
                columns = [row[0] for row in cursor.fetchall()]
                assert columns == ["previous_finished_at", "reverse_result"]
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'source_policy_requests' AND column_name = 'hold_expires_at'
                    """
                )
                assert cursor.fetchone() is not None
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()
