"""Add relay applications, encrypted probe configuration and sample history.

Run with the new API image before switching API containers. Safe to run twice;
existing relays remain approved, with monitoring disabled and no credentials.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.services.db_migration import ensure_relay_monitoring


def migrate(engine) -> None:
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if not {"users", "relay_stations"}.issubset(tables):
            raise RuntimeError("v22 requires existing users and relay_stations tables")
        ensure_relay_monitoring(connection)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    engine = create_engine(args.database_url)
    try:
        migrate(engine)
    finally:
        engine.dispose()
    print("Relay applications and monitoring v22 migration complete")


if __name__ == "__main__":
    main()
