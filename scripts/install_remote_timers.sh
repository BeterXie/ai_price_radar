#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi
set +a
if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

install -d -m 0700 -o 10001 -g 10001 "$ROOT/data/crawler"
install -m 0644 "$ROOT"/deploy/systemd/ai-price-radar-*.service /etc/systemd/system/
install -m 0644 "$ROOT"/deploy/systemd/ai-price-radar-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ai-price-radar-discover.timer
if [[ "${LDXP_COLLECTION_ENABLED:-false}" == "true" ]]; then
  systemctl enable --now \
    ai-price-radar-refresh.timer \
    ai-price-radar-inventory.timer
else
  systemctl disable --now ai-price-radar-refresh.timer ai-price-radar-inventory.timer 2>/dev/null || true
  echo "LDXP collection disabled by policy; refresh/inventory timers left disabled"
fi
systemctl list-timers --all 'ai-price-radar-*'
