"""Create brand publishing tables without changing shared products or snapshots."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.site_models import SiteAd, SiteArticle, SiteRelay


def migrate(engine) -> None:
    with engine.begin() as connection:
        if "relay_stations" not in inspect(connection).get_table_names():
            raise RuntimeError("Brand publishing requires the existing relay catalog")
        for table in (SiteArticle.__table__, SiteAd.__table__, SiteRelay.__table__):
            table.create(connection, checkfirst=True)


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
    print("Brand publishing v26 migration complete")
