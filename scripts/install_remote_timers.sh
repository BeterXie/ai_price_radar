#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi

install -d -m 0700 -o 10001 -g 10001 "$ROOT/data/crawler"
install -m 0644 "$ROOT"/deploy/systemd/ai-price-radar-*.service /etc/systemd/system/
install -m 0644 "$ROOT"/deploy/systemd/ai-price-radar-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now \
  ai-price-radar-refresh.timer \
  ai-price-radar-inventory.timer \
  ai-price-radar-discover.timer
systemctl list-timers --all 'ai-price-radar-*'
