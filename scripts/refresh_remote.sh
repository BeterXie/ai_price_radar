#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-scan}"
DATA_DIR="$ROOT/data/crawler"
CRAWLER_DB="$DATA_DIR/ldxp_crawler.db"
MERCHANT_SOURCES="$DATA_DIR/merchant_sources.json"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.pricememo.yml)
CRAWLER_CONTAINER_NAME="ai-price-radar-crawler-run-${MODE}"
KEYWORDS=(gpt chatgpt "chatgpt plus" "chatgpt pro" "chatgpt team" "chatgpt business" "openai api" codex claude "claude pro" "claude api" anthropic gemini "gemini advanced" "google one ai" "gemini api" grok supergrok "xai api" "x.ai" cursor windsurf augment "github copilot" 账号 成品号 代充 直充 团队席位 车位 卡密 兑换码 API 额度 中转 自动发货 "open ai" "x premium" "twitter premium" "推特会员" "chat plus" "gpt plus" "gpt team")

cleanup_crawler_container() {
  docker rm -f "$CRAWLER_CONTAINER_NAME" >/dev/null 2>&1 || true
}

cleanup_browser_profile_singletons() {
  local profile="$DATA_DIR/browser_profile"
  local name path
  for name in SingletonLock SingletonSocket SingletonCookie; do
    path="$profile/$name"
    if [[ -L "$path" ]]; then
      unlink "$path"
    elif [[ -e "$path" ]]; then
      echo "refusing to remove non-symlink browser profile singleton: $path" >&2
      return 6
    fi
  done
}

trap 'cleanup_crawler_container' EXIT
trap 'exit 143' TERM INT HUP

mkdir -p "$DATA_DIR/output" "$DATA_DIR/backups"
chown 10001:10001 "$DATA_DIR" "$DATA_DIR/output"
chmod 700 "$DATA_DIR" "$DATA_DIR/output" "$DATA_DIR/backups"
exec 9>"$DATA_DIR/.refresh.lock"
if ! flock -n 9; then
  echo "another crawler refresh is already running; this schedule was skipped"
  exit 0
fi

run_crawler() {
  cleanup_crawler_container
  "${COMPOSE[@]}" run --rm --name "$CRAWLER_CONTAINER_NAME" crawler "$@"
}

run_browser_crawler() {
  cleanup_crawler_container
  cleanup_browser_profile_singletons
  "${COMPOSE[@]}" run --rm --name "$CRAWLER_CONTAINER_NAME" --entrypoint xvfb-run crawler \
    -a python ldxp_gpt_crawler.py "$@"
}

run_dujiao_discovery() {
  run_crawler discover-dujiao \
    --db /data/ldxp_crawler.db \
    --seed-file /config/dujiao_seeds.txt \
    --sources "${DISCOVERY_DUJIAO_SOURCES:-seed,bing,github}" \
    --bing-pages "${DISCOVERY_BING_PAGES:-5}" \
    --bing-count "${DISCOVERY_BING_COUNT:-30}" \
    --github-pages "${DISCOVERY_GITHUB_PAGES:-3}" \
    --github-count "${DISCOVERY_GITHUB_COUNT:-100}" \
    --github-max-candidates "${DISCOVERY_GITHUB_MAX_CANDIDATES:-300}" \
    --max-new-candidates "${DISCOVERY_MAX_NEW_CANDIDATES:-1000}" \
    --max-processed-candidates "${DISCOVERY_MAX_PROCESSED_CANDIDATES:-3000}" \
    --reverify-stale-hours "${DISCOVERY_REVERIFY_STALE_HOURS:-24}" \
    --request-interval "${DISCOVERY_REQUEST_INTERVAL_SECONDS:-2}" \
    --keywords "${KEYWORDS[@]}"
}

run_source_discovery() {
  run_crawler discover-sources \
    --db /data/ldxp_crawler.db \
    --seed-file /config/general_seeds.txt \
    --api-url "${DISCOVERY_API_URL:-http://api:8000}" \
    --worker-key "${DISCOVERY_WORKER_KEY:-}" \
    --sources "${DISCOVERY_SOURCES:-seed,bing,github,commoncrawl}" \
    --max-raw-urls "${DISCOVERY_MAX_RAW_URLS:-2000}" \
    --max-unique-candidates "${DISCOVERY_MAX_NEW_CANDIDATES:-1000}" \
    --request-interval "${DISCOVERY_REQUEST_INTERVAL_SECONDS:-2}" \
    --bing-pages "${DISCOVERY_BING_PAGES:-5}" \
    --bing-count "${DISCOVERY_BING_COUNT:-30}" \
    --bing-delay "${DISCOVERY_BING_DELAY_SECONDS:-2}" \
    --github-pages "${DISCOVERY_GITHUB_PAGES:-3}" \
    --github-count "${DISCOVERY_GITHUB_COUNT:-100}" \
    --github-max-candidates "${DISCOVERY_GITHUB_MAX_CANDIDATES:-300}" \
    --cc-indexes "${DISCOVERY_COMMONCRAWL_INDEXES:-2}" \
    --cc-max-urls "${DISCOVERY_COMMONCRAWL_MAX_URLS:-500}" \
    --keywords "${KEYWORDS[@]}"
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
    run_dujiao_discovery
    if [[ -n "${DISCOVERY_WORKER_KEY:-}" ]]; then
      run_source_discovery
    else
      echo "DISCOVERY_WORKER_KEY is empty; unified source discovery skipped"
    fi
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
    run_dujiao_discovery
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

PUBLISH_ARGS=(
  python publish_catalog.py
  --ldxp-db /tmp/ldxp_crawler.db
  --dujiao-db /tmp/ldxp_crawler.db
)
if [[ -f "$MERCHANT_SOURCES" ]]; then
  PUBLISH_ARGS+=(--merchant-sources /workspace/data/crawler/merchant_sources.json)
fi

docker run --rm --user 0 \
  --network ai-price-radar_default \
  --env-file "$ROOT/.env" \
  -v "$ROOT:/workspace:ro" \
  -v "$BACKUP_DB:/tmp/ldxp_crawler.db:ro" \
  -w /workspace/pipeline \
  ai-price-radar-importer \
  "${PUBLISH_ARGS[@]}"
