#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-scan}"
DATA_DIR="$ROOT/data/crawler"
CRAWLER_DB="$DATA_DIR/ldxp_crawler.db"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.pricememo.yml)
KEYWORDS=(gpt chatgpt openai "open ai" codex claude gemini "google one ai" grok supergrok xai "x.ai" "x premium" "twitter premium" "推特会员" "chat plus" "gpt plus" "gpt team")

mkdir -p "$DATA_DIR/output" "$DATA_DIR/backups"
chown 10001:10001 "$DATA_DIR" "$DATA_DIR/output"
chmod 700 "$DATA_DIR" "$DATA_DIR/output" "$DATA_DIR/backups"
exec 9>"$DATA_DIR/.refresh.lock"
if ! flock -n 9; then
  echo "another crawler refresh is already running; this schedule was skipped"
  exit 0
fi

run_crawler() {
  "${COMPOSE[@]}" run --rm crawler "$@"
}

run_browser_crawler() {
  "${COMPOSE[@]}" run --rm --entrypoint xvfb-run crawler \
    -a python ldxp_gpt_crawler.py "$@"
}

case "$MODE" in
  discover)
    run_crawler discover \
      --db /data/ldxp_crawler.db \
      --keywords "${KEYWORDS[@]}" \
      --seed-file /config/seeds.txt \
      --sources seed,bing,commoncrawl \
      --bing-pages 5 \
      --cc-indexes 3 \
      --max-discovered 500
    exit 0
    ;;
  full)
    run_browser_crawler all \
      --db /data/ldxp_crawler.db \
      --rescan \
      --keywords "${KEYWORDS[@]}" \
      --seed-file /config/seeds.txt \
      --sources seed,bing,commoncrawl \
      --max-discovered 500 \
      --browser-profile /data/browser_profile \
      --storage-state /data/browser_state.json \
      --output-dir /data/output \
      --limit 100 \
      --request-interval 2.0 \
      --manual-challenge-seconds 0 \
      --circuit-breaker 3
    ;;
  inventory)
    if [[ ! -f "$CRAWLER_DB" ]]; then
      echo "crawler database is missing; inventory scan skipped"
      exit 0
    fi
    run_browser_crawler scan \
      --db /data/ldxp_crawler.db \
      --rescan \
      --matched-only \
      --keywords "${KEYWORDS[@]}" \
      --browser-profile /data/browser_profile \
      --storage-state /data/browser_state.json \
      --limit 25 \
      --request-interval 2.0 \
      --manual-challenge-seconds 0 \
      --circuit-breaker 3
    ;;
  scan)
    if [[ ! -f "$CRAWLER_DB" ]]; then
      echo "crawler database is missing; run '$0 full' once first" >&2
      exit 2
    fi
    run_browser_crawler scan \
      --db /data/ldxp_crawler.db \
      --rescan \
      --keywords "${KEYWORDS[@]}" \
      --browser-profile /data/browser_profile \
      --storage-state /data/browser_state.json \
      --limit 100 \
      --request-interval 2.0 \
      --manual-challenge-seconds 0 \
      --circuit-breaker 3
    ;;
  *)
    echo "usage: $0 {full|scan|inventory|discover}" >&2
    exit 2
    ;;
esac

SUMMARY="$(python3 - "$CRAWLER_DB" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect(sys.argv[1])
db.row_factory = sqlite3.Row
check = db.execute("PRAGMA quick_check").fetchone()[0]
row = db.execute("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()
if check != "ok" or row is None:
    raise SystemExit("crawler database validation failed")
print(json.dumps({
    "run_id": row["id"],
    "attempted": row["attempted"],
    "successful": row["successful"],
    "failed": row["failed"],
    "blocked": row["blocked"],
    "matches": row["matches"],
    "circuit_broken": bool(row["circuit_broken"]),
}, ensure_ascii=False))
db.close()
PY
)"
echo "scan summary: $SUMMARY"

SUCCESSFUL="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["successful"])' "$SUMMARY")"
if [[ "$SUCCESSFUL" -eq 0 ]]; then
  echo "scan had no successful shops; production import skipped" >&2
  exit 4
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DB="$DATA_DIR/backups/ldxp_crawler_${STAMP}.db"
sqlite3 "$CRAWLER_DB" ".backup '$BACKUP_DB'"
if [[ "$(sqlite3 "$BACKUP_DB" 'PRAGMA quick_check;')" != "ok" ]]; then
  echo "crawler database backup validation failed" >&2
  exit 5
fi
find "$DATA_DIR/backups" -maxdepth 1 -type f -name 'ldxp_crawler_*.db' \
  ! -path "$BACKUP_DB" -delete

docker run --rm --user 0 \
  --network ai-price-radar_default \
  --env-file "$ROOT/.env" \
  -v "$ROOT:/workspace:ro" \
  -v "$BACKUP_DB:/tmp/ldxp_crawler.db:ro" \
  -w /workspace/pipeline \
  ai-price-radar-api \
  python sync_ldxp.py --source-db /tmp/ldxp_crawler.db
