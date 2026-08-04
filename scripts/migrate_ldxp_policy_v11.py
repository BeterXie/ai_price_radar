from __future__ import annotations

import argparse
import os

import psycopg

from scripts.migrate_source_intake_v8 import connection_url


DDL = """
CREATE TABLE IF NOT EXISTS source_policy_requests (
    id BIGSERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    request_type VARCHAR(20) NOT NULL DEFAULT 'opt_out',
    requester_email VARCHAR(200) NOT NULL,
    requester_ip VARCHAR(64) NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    temporary_hold_at TIMESTAMPTZ,
    hold_expires_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,
    decision_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE source_policy_requests DROP CONSTRAINT IF EXISTS ck_source_policy_requests_type;
ALTER TABLE source_policy_requests ADD CONSTRAINT ck_source_policy_requests_type CHECK (
    request_type IN ('opt_out', 'correction', 'ownership')
);
ALTER TABLE source_policy_requests DROP CONSTRAINT IF EXISTS ck_source_policy_requests_status;
ALTER TABLE source_policy_requests ADD CONSTRAINT ck_source_policy_requests_status CHECK (
    status IN ('pending_unverified', 'pending', 'verified', 'applied', 'rejected')
);
ALTER TABLE source_policy_requests ADD COLUMN IF NOT EXISTS requester_ip VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE source_policy_requests ADD COLUMN IF NOT EXISTS hold_expires_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_source_policy_requests_status ON source_policy_requests(status);

CREATE TABLE IF NOT EXISTS source_policy_control (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_policy_effects (
    id BIGSERIAL PRIMARY KEY,
    policy_request_id BIGINT NOT NULL REFERENCES source_policy_requests(id) ON DELETE CASCADE,
    intake_id BIGINT NOT NULL,
    previous_status VARCHAR(30) NOT NULL,
    previous_finished_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reversed_at TIMESTAMPTZ,
    reverse_result VARCHAR(30) NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_source_policy_effects_request ON source_policy_effects(policy_request_id);

DO $$
BEGIN
    IF to_regclass('source_intakes') IS NOT NULL THEN
        ALTER TABLE source_policy_effects DROP CONSTRAINT IF EXISTS fk_source_policy_effects_intake;
        ALTER TABLE source_policy_effects
            ADD CONSTRAINT fk_source_policy_effects_intake
            FOREIGN KEY (intake_id) REFERENCES source_intakes(id) ON DELETE CASCADE;
    END IF;
END $$;
"""


def migrate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create v11 source policy request and control tables")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        migrate(connection)
        connection.commit()
    print("source policy v11 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
