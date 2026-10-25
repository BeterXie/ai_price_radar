"""Add empty relay metadata, manual groups and durable icon cache; preserve existing data."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.services.db_migration import ensure_relay_model_catalog


def migrate(engine) -> None:
    with engine.begin() as connection:
        if "relay_stations" not in inspect(connection).get_table_names():
            raise RuntimeError("v24 requires relay_stations; run v22 first")
        ensure_relay_model_catalog(connection)


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
    print("Relay model catalog v24 migration complete")


if __name__ == "__main__":
    main()
