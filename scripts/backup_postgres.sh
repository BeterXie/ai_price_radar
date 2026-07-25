#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"
umask 077
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="$BACKUP_DIR/price_radar_${STAMP}.sql.gz"
TEMP="$TARGET.tmp.$$"
trap 'rm -f "$TEMP"' EXIT

docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$TEMP"

test -s "$TEMP"
gzip -t "$TEMP"
mv "$TEMP" "$TARGET"
trap - EXIT
echo "backup: $TARGET"
