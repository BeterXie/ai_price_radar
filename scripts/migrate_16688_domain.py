"""Move stored 16688 URLs to .store without changing identities or observations.

Pause discovery, detection and publication before --apply. Dry-run is the default;
identity collisions abort the entire transaction and require manual review.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from sqlalchemy import MetaData, Table, create_engine, select, text, update

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps" / "api"), str(ROOT / "shared_http")]
from app.services.source_discovery import candidate_key_for
from price_radar_http.platform_16688 import canonical_url


URL_COLUMNS = {
    "source_intakes": ("source_url", "source_key"),
    "source_candidates": ("discovered_url", "canonical_url", "canonical_origin",
                          "detected_source_url", "detected_source_key"),
    "shops": ("source_url",),
    "raw_products": ("source_url",),
    "offers": ("source_url",),
    "ad_slots": ("link_url", "image_url"),
}


def migrate(engine, *, apply: bool = False) -> dict[str, int]:
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SET LOCAL lock_timeout='15s'"))
            if apply:
                conn.execute(text("LOCK TABLE " + ", ".join(URL_COLUMNS) + " IN SHARE ROW EXCLUSIVE MODE"))
        metadata = MetaData()
        tables = {name: Table(name, metadata, autoload_with=conn) for name in URL_COLUMNS}
        plans = {}
        for name, columns in URL_COLUMNS.items():
            table = tables[name]
            selected = [table.c.id, *(table.c[column] for column in columns)]
            if name == "source_candidates":
                selected.extend([table.c.candidate_key, table.c.platform_hint])
            if name == "source_intakes":
                selected.append(table.c.source_type)
            stmt = select(*selected)
            if name == "shops":
                stmt = stmt.where(table.c.platform == "16688")
            elif name in {"raw_products", "offers"}:
                shops = tables["shops"]
                stmt = stmt.where(table.c.shop_id.in_(select(shops.c.id).where(shops.c.platform == "16688")))
            rows = list(conn.execute(stmt).mappings())
            changes = []
            for row in rows:
                values = {column: canonical_url(row[column]) for column in columns if row[column]}
                values = {key: value for key, value in values.items() if row[key] != value}
                if name == "source_candidates" and "canonical_url" in values:
                    values["candidate_key"] = candidate_key_for(values["canonical_url"], row["platform_hint"])
                if values:
                    changes.append((row["id"], values))
            if name in {"source_intakes", "source_candidates"}:
                identities = {}
                changed = dict(changes)
                for row in rows:
                    values = changed.get(row["id"], {})
                    key = ((row["source_type"], values.get("source_key", row["source_key"]))
                           if name == "source_intakes" else values.get("candidate_key", row["candidate_key"]))
                    if key in identities:
                        raise ValueError(f"{name} identity collision: {identities[key]} and {row['id']}")
                    identities[key] = row["id"]
            plans[name] = changes
        if apply:
            for name, changes in plans.items():
                table = tables[name]
                for identity, values in changes:
                    conn.execute(update(table).where(table.c.id == identity).values(**values))
        return {name: len(changes) for name, changes in plans.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("DATABASE_URL is required")
    engine = create_engine(args.database_url)
    try:
        counts = migrate(engine, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps({"applied": args.apply, "updated_rows": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
