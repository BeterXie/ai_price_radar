from __future__ import annotations

import argparse
import os

import psycopg

from scripts.migrate_source_intake_v8 import connection_url


DDL = """
CREATE TABLE IF NOT EXISTS source_discovery_runs (
    id BIGSERIAL PRIMARY KEY,
    trigger VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    adapters JSON NOT NULL DEFAULT '[]',
    status VARCHAR(30) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    discovered_raw_count INTEGER NOT NULL DEFAULT 0,
    normalized_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    new_candidate_count INTEGER NOT NULL DEFAULT 0,
    reverified_count INTEGER NOT NULL DEFAULT 0,
    detected_count INTEGER NOT NULL DEFAULT 0,
    ai_matched_count INTEGER NOT NULL DEFAULT 0,
    auto_approved_count INTEGER NOT NULL DEFAULT 0,
    pending_review_count INTEGER NOT NULL DEFAULT 0,
    validation_failed_count INTEGER NOT NULL DEFAULT 0,
    promoted_intake_count INTEGER NOT NULL DEFAULT 0,
    adapter_stats JSON NOT NULL DEFAULT '{}',
    platform_stats JSON NOT NULL DEFAULT '{}',
    failure_stats JSON NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE source_discovery_runs DROP CONSTRAINT IF EXISTS ck_source_discovery_runs_status;
ALTER TABLE source_discovery_runs ADD CONSTRAINT ck_source_discovery_runs_status CHECK (
    status IN ('running', 'succeeded', 'partial', 'failed')
);

CREATE INDEX IF NOT EXISTS ix_source_discovery_runs_status_started
    ON source_discovery_runs(status, started_at);
CREATE INDEX IF NOT EXISTS ix_source_discovery_runs_finished
    ON source_discovery_runs(finished_at);

CREATE TABLE IF NOT EXISTS source_candidates (
    id BIGSERIAL PRIMARY KEY,
    candidate_key VARCHAR(300) NOT NULL,
    canonical_origin TEXT NOT NULL DEFAULT '',
    discovered_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    platform_hint VARCHAR(30) NOT NULL DEFAULT 'unknown',
    detected_platform VARCHAR(30) NOT NULL DEFAULT 'unknown',
    detected_source_key VARCHAR(300) NOT NULL DEFAULT '',
    detected_source_url TEXT NOT NULL DEFAULT '',
    discovery_sources JSON NOT NULL DEFAULT '[]',
    matched_queries JSON NOT NULL DEFAULT '[]',
    fingerprints JSON NOT NULL DEFAULT '[]',
    sample_products JSON NOT NULL DEFAULT '[]',
    total_product_count INTEGER NOT NULL DEFAULT 0,
    ai_product_count INTEGER NOT NULL DEFAULT 0,
    confidence_score INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'discovered',
    failure_reason TEXT NOT NULL DEFAULT '',
    decision_note TEXT NOT NULL DEFAULT '',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_verified_at TIMESTAMPTZ,
    next_verify_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    promoted_intake_id BIGINT REFERENCES source_intakes(id) ON DELETE SET NULL,
    discovery_run_id BIGINT REFERENCES source_discovery_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE source_candidates DROP CONSTRAINT IF EXISTS uq_source_candidates_key;
ALTER TABLE source_candidates ADD CONSTRAINT uq_source_candidates_key UNIQUE (candidate_key);

ALTER TABLE source_candidates DROP CONSTRAINT IF EXISTS ck_source_candidates_status;
ALTER TABLE source_candidates ADD CONSTRAINT ck_source_candidates_status CHECK (
    status IN (
        'discovered', 'queued', 'detecting', 'detected', 'no_match',
        'validation_failed', 'pending_review', 'auto_approved', 'promoted',
        'rejected', 'needs_re_review', 'disabled'
    )
);

ALTER TABLE source_candidates DROP CONSTRAINT IF EXISTS ck_source_candidates_platform;
ALTER TABLE source_candidates ADD CONSTRAINT ck_source_candidates_platform CHECK (
    detected_platform IN (
        'unknown', 'ldxp', 'dujiao_next', 'merchant_json',
        'woocommerce', 'schema_org', 'other'
    )
);

CREATE INDEX IF NOT EXISTS ix_source_candidates_status_next_verify
    ON source_candidates(status, next_verify_at);
CREATE INDEX IF NOT EXISTS ix_source_candidates_platform_status
    ON source_candidates(detected_platform, status);
CREATE INDEX IF NOT EXISTS ix_source_candidates_promoted_intake
    ON source_candidates(promoted_intake_id);
CREATE INDEX IF NOT EXISTS ix_source_candidates_last_seen
    ON source_candidates(last_seen_at);
CREATE INDEX IF NOT EXISTS ix_source_candidates_lease
    ON source_candidates(lease_expires_at);
"""


def migrate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL)


def _summary(connection: psycopg.Connection) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM information_schema.tables
                WHERE table_name='source_discovery_runs'),
              (SELECT count(*) FROM information_schema.tables
                WHERE table_name='source_candidates'),
              (SELECT count(*) FROM source_candidates)
            """
        )
        runs_table, candidates_table, candidate_rows = cursor.fetchone()
    return (
        f"source_discovery_runs_table={runs_table} "
        f"source_candidates_table={candidates_table} "
        f"source_candidates_rows={candidate_rows}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create v10 unified source discovery tables")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        print(f"before: {_summary(connection)}")
        migrate(connection)
        connection.commit()
        print(f"after: {_summary(connection)}")
    print("source discovery v10 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
