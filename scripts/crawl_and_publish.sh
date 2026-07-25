#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CRAWLER_DB="${CRAWLER_DB:-$ROOT/ldxp_crawler.db}"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://price_radar:change-me-now@localhost:5432/price_radar}"

python crawler/ldxp/ldxp_gpt_crawler.py scan \
  --db "$CRAWLER_DB" \
  --keywords gpt chatgpt openai codex \
  --request-interval 2.0 \
  --circuit-breaker 3

python pipeline/sync_ldxp.py \
  --source-db "$CRAWLER_DB" \
  --database-url "$DATABASE_URL"
