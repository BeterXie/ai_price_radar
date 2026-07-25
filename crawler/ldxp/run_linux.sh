#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --disable-pip-version-check -r requirements.txt
python -m playwright install chromium
python ldxp_gpt_crawler.py all \
  --keywords gpt chatgpt openai codex "gpt plus" "gpt team" \
  --seed-file seeds.txt \
  --sources seed,bing,commoncrawl \
  --request-interval 2.0 \
  --circuit-breaker 3
