# AI Price Radar v3.7.6 — Crawler Request Timeout Hotfix

This patch prevents one unresponsive shop API request from blocking the production crawler and every later catalog publication.

## What changed

- Added a browser-side abort deadline to replayed shop API requests, using the crawler's existing `--timeout` value.
- Kept timeout failures on the existing `network_error` path so later shops continue and the current retry policy remains authoritative.
- Removed stale Chromium singleton symlinks before browser refresh startup and extended the inventory service budget to one hour so atomic publication can complete after scanning.
- Aligned release metadata on `3.7.6`.

## Validation

- Crawler self-test and pytest coverage must pass.
- API tests and Web typecheck must pass before tagging.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.6` Tag after CI succeeds.
- Rebuild the Crawler image and complete one full multi-source publication before restoring production timers.
