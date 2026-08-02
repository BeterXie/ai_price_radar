#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CRAWLER_DB="${CRAWLER_DB:-$ROOT/ldxp_crawler.db}"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://price_radar:change-me-now@localhost:5432/price_radar}"
MERCHANT_SOURCES="${MERCHANT_SOURCES:-}"

python crawler/ldxp/ldxp_gpt_crawler.py scan \
  --db "$CRAWLER_DB" \
  --keywords gpt chatgpt openai codex \
  --request-interval 2.0 \
  --circuit-breaker 3

PUBLISH_ARGS=(
  python pipeline/publish_catalog.py
  --ldxp-db "$CRAWLER_DB"
  --dujiao-db "$CRAWLER_DB"
  --database-url "$DATABASE_URL"
)
if [[ -n "$MERCHANT_SOURCES" ]]; then
  PUBLISH_ARGS+=(--merchant-sources "$MERCHANT_SOURCES")
fi
"${PUBLISH_ARGS[@]}"
