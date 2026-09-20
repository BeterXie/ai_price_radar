#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
# 保留最近 N 份备份，防止备份目录无限增长；0 表示禁用清理。
BACKUP_KEEP_COUNT="${BACKUP_KEEP_COUNT:-14}"
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

if [ "$BACKUP_KEEP_COUNT" -gt 0 ]; then
  find "$BACKUP_DIR" -maxdepth 1 -name 'price_radar_*.sql.gz' -type f | sort -r \
    | tail -n +"$((BACKUP_KEEP_COUNT + 1))" \
    | while IFS= read -r old_backup; do
        rm -f -- "$old_backup"
        echo "backup: pruned $(basename "$old_backup")"
      done
fi
