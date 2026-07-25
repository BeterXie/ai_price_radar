#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "usage: $0 BACKUP.sql.gz [TARGET_DB]" >&2
  exit 2
fi

SOURCE_DB="${POSTGRES_DB:-$(docker compose exec -T db printenv POSTGRES_DB | tr -d '\r')}"
TARGET_DB="${2:-${SOURCE_DB}_restore_test}"
DB_USER="${POSTGRES_USER:-$(docker compose exec -T db printenv POSTGRES_USER | tr -d '\r')}"

if [[ ! "$TARGET_DB" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "target database name may only contain letters, digits, and underscores" >&2
  exit 2
fi
if [[ "$TARGET_DB" != *_restore_test && "${ALLOW_RESTORE_OVERWRITE:-0}" != "1" ]]; then
  echo "refusing non-test target; use a *_restore_test database or set ALLOW_RESTORE_OVERWRITE=1" >&2
  exit 2
fi
if [[ "$TARGET_DB" == "$SOURCE_DB" && "${ALLOW_RESTORE_OVERWRITE:-0}" != "1" ]]; then
  echo "refusing to overwrite the configured database" >&2
  exit 2
fi

gzip -t "$BACKUP_FILE"
docker compose exec -T db dropdb --if-exists --force -U "$DB_USER" "$TARGET_DB"
docker compose exec -T db createdb -U "$DB_USER" "$TARGET_DB"
gzip -dc "$BACKUP_FILE" | docker compose exec -T db \
  psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TARGET_DB"

TABLE_COUNT="$(docker compose exec -T db psql -At -U "$DB_USER" -d "$TARGET_DB" \
  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
if [[ ! "$TABLE_COUNT" =~ ^[1-9][0-9]*$ ]]; then
  echo "restore verification failed: no public tables found" >&2
  exit 1
fi
echo "restore verified: database=$TARGET_DB public_tables=$TABLE_COUNT"
