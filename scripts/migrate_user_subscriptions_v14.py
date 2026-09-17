from __future__ import annotations

import argparse
import os

import psycopg


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


DDL = """
CREATE TABLE IF NOT EXISTS user_product_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_slug VARCHAR(120) NOT NULL REFERENCES products(slug) ON DELETE CASCADE,
    target_price NUMERIC(10, 2),
    notify_email BOOLEAN NOT NULL DEFAULT true,
    notify_bot BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_product_subscription UNIQUE(user_id, product_slug)
);
CREATE INDEX IF NOT EXISTS ix_user_product_subs_user_id ON user_product_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_product_subs_product_slug ON user_product_subscriptions(product_slug);

ALTER TABLE user_bot_bindings ADD COLUMN IF NOT EXISTS bot_token TEXT DEFAULT '';
ALTER TABLE user_bot_bindings ADD COLUMN IF NOT EXISTS extra_meta JSONB DEFAULT '{}'::jsonb;
"""


def migrate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create user product subscriptions table and extend bot bindings v14")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        migrate(connection)
        connection.commit()
    print("User product subscriptions v14 migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
