#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
test "$VERSION" = "3.2.0"
grep -q "VERSION = \"$VERSION\"" "$ROOT/apps/api/app/main.py"
grep -q "\"version\": \"$VERSION\"" "$ROOT/apps/web/package.json"
(
  cd "$ROOT/apps/api"
  python -m pytest -q
)
(
  cd "$ROOT/pipeline"
  python -m pytest -q
)
(
  cd "$ROOT/apps/web"
  npm ci
  npm run typecheck
  npm run build
)
echo "AI Price Radar v$VERSION release checks passed"
