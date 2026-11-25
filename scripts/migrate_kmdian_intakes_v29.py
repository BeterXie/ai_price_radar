"""Allow platform-verified KMDian submissions; existing records remain unchanged."""
import argparse
import os
from sqlalchemy import create_engine, text


def migrate(engine):
    if engine.dialect.name != "postgresql":
        raise ValueError("v29 updates a PostgreSQL check constraint")
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout='15s'"))
        conn.execute(text("ALTER TABLE source_intakes DROP CONSTRAINT IF EXISTS ck_source_intakes_type"))
        conn.execute(text("""ALTER TABLE source_intakes ADD CONSTRAINT ck_source_intakes_type
            CHECK (source_type IN ('unknown','ldxp','merchant_json','dujiao_next','woocommerce',
            '16688','kmdian','schema_org','acg_faka','other'))"""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:parser.error("DATABASE_URL is required")
    engine = create_engine(args.database_url)
    try:migrate(engine)
    finally:engine.dispose()
    print("KMDian intake v29 migration complete")
