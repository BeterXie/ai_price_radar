from __future__ import annotations

import argparse
import os

import psycopg


def connection_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


DDL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE,
    nickname VARCHAR(100) NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    qq_openid VARCHAR(128) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_qq_openid ON users(qq_openid);

CREATE TABLE IF NOT EXISTS user_sessions (
    token VARCHAR(64) PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_sessions_expires_at ON user_sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_codes (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(200) NOT NULL,
    code VARCHAR(20) NOT NULL,
    purpose VARCHAR(30) NOT NULL DEFAULT 'login',
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_auth_codes_email ON auth_codes(email);
CREATE INDEX IF NOT EXISTS ix_auth_codes_expires_at ON auth_codes(expires_at);

CREATE TABLE IF NOT EXISTS user_bot_bindings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL DEFAULT 'qq',
    target_id VARCHAR(128) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    notify_price_drop BOOLEAN NOT NULL DEFAULT true,
    notify_price_hike BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_bot_binding UNIQUE(user_id, channel)
);
CREATE INDEX IF NOT EXISTS ix_user_bot_bindings_user_id ON user_bot_bindings(user_id);
CREATE INDEX IF NOT EXISTS ix_user_bot_bindings_channel ON user_bot_bindings(channel);
CREATE INDEX IF NOT EXISTS ix_user_bot_bindings_target_id ON user_bot_bindings(target_id);

INSERT INTO system_settings (key, value, updated_at)
VALUES ('bot_enabled', 'true', now())
ON CONFLICT (key) DO NOTHING;
"""


def migrate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create user auth and bot binding tables v13")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    with psycopg.connect(connection_url(args.database_url)) as connection:
        migrate(connection)
        connection.commit()
    print("User auth and bot binding tables v13 migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
