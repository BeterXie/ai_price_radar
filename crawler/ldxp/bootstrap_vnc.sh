#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  kill "${WEBSOCKIFY_PID:-}" "${X11VNC_PID:-}" "${XVFB_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

Xvfb :99 -screen 0 1365x900x24 -ac -noreset >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 1
x11vnc -display :99 -forever -shared -nopw -localhost -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
X11VNC_PID=$!
websockify --web=/usr/share/novnc 0.0.0.0:6080 localhost:5900 >/tmp/websockify.log 2>&1 &
WEBSOCKIFY_PID=$!

echo "Remote browser is available through the SSH-only noVNC endpoint on port 6080."
python ldxp_gpt_crawler.py bootstrap \
  --db /data/ldxp_crawler.db \
  --browser-profile /data/browser_profile \
  --storage-state /data/browser_state.json \
  --manual-challenge-seconds 1800 \
  --request-interval 2.0 \
  --circuit-breaker 1
