from __future__ import annotations

import argparse
import os

import psycopg

from scripts.migrate_source_intake_v8 import connection_url


DDL = """
ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_type;
ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type CHECK (
    source_type IN (
        'unknown', 'ldxp', 'merchant_json', 'dujiao_next',
        'woocommerce', '16688', 'schema_org', 'other'
    )
);

ALTER TABLE source_candidates DROP CONSTRAINT IF EXISTS ck_source_candidates_platform;
ALTER TABLE source_candidates ADD CONSTRAINT ck_source_candidates_platform CHECK (
    detected_platform IN (
        'unknown', 'ldxp', 'dujiao_next', 'merchant_json',
        'woocommerce', '16688', 'schema_org', 'other'
    )
);
"""


def migrate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Allow 16688 source intakes and discovery candidates")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        migrate(connection)
        connection.commit()
    print("16688 source platform v11 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
