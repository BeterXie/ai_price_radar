"""Create persistent collector jobs without importing application settings."""
import argparse
import os
from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, String, Table, UniqueConstraint, create_engine, text


def migrate(engine):
    table = Table("collector_jobs", MetaData(),
        Column("id", String(36), primary_key=True), Column("kind", String(20), nullable=False),
        Column("active_lane", String(20)), Column("status", String(20), nullable=False, server_default="queued", index=True),
        Column("release", String(30), nullable=False), Column("sources", JSON, nullable=False, server_default="[]"),
        Column("worker_id", String(80), nullable=False, server_default=""),
        Column("lease_token", String(64), nullable=False, server_default=""), Column("lease_expires_at", DateTime(timezone=True)),
        Column("attempts", Integer, nullable=False, server_default="0"),
        Column("result_file", String(100), nullable=False, server_default=""),
        Column("result_summary", JSON, nullable=False, server_default="{}"), Column("error", String(500), nullable=False, server_default=""),
        Column("published_snapshot_id", Integer),
        Column("baseline_snapshot_id", Integer), Column("followup_kind", String(20), nullable=False, server_default=""),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
        UniqueConstraint("active_lane", name="uq_collector_active_lane"))
    with engine.begin() as conn:
        table.create(conn, checkfirst=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("DATABASE_URL is required")
    engine = create_engine(args.database_url)
    try:
        migrate(engine)
    finally:
        engine.dispose()
    print("Collector jobs v28 migration complete")
