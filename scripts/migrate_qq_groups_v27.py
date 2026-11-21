"""Create QQ group subscriptions; existing private bindings are unchanged."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.services.db_migration import ensure_qq_group_subscriptions


def migrate(engine) -> None:
    with engine.begin() as connection:
        ensure_qq_group_subscriptions(connection)


if __name__ == "__main__":
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
    print("QQ group subscription v27 migration complete")
