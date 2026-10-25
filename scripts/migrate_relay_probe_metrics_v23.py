"""Add nullable relay connection, first-text and cache usage measurements.

Run after v22 with the new API image before switching containers. Repeating
this migration preserves all existing samples and never fabricates metrics.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.services.db_migration import ensure_relay_probe_metrics


def migrate(engine) -> None:
    with engine.begin() as connection:
        if "relay_probe_results" not in inspect(connection).get_table_names():
            raise RuntimeError("v23 requires relay_probe_results; run v22 first")
        ensure_relay_probe_metrics(connection)


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
    print("Relay probe metrics v23 migration complete")


if __name__ == "__main__":
    main()
