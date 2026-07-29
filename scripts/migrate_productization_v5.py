from __future__ import annotations

import argparse
import os

import psycopg

DDL = """
ALTER TABLE reports ADD COLUMN IF NOT EXISTS public_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS merchant_response TEXT NOT NULL DEFAULT '';
ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ NULL;
CREATE INDEX IF NOT EXISTS ix_reports_status_resolved_at ON reports (status, resolved_at DESC);
"""


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add public correction-log fields for v3.2.0")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            cursor.execute("UPDATE reports SET resolved_at = created_at WHERE status = 'resolved' AND resolved_at IS NULL")
        connection.commit()
    print("productization v5 migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
