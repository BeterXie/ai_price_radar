"""Add nullable candy/cache benchmark metadata after v23; safe to repeat."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.services.db_migration import ensure_relay_benchmark


def migrate(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "relay_probe_results" not in inspector.get_table_names() or "cached_input_tokens" not in {c["name"] for c in inspector.get_columns("relay_probe_results")}:
            raise RuntimeError("v25 requires relay probe metrics; run v23 first")
        ensure_relay_benchmark(connection)


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
    print("Relay benchmark v25 migration complete")


if __name__ == "__main__":
    main()
