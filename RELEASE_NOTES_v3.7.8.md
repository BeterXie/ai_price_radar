# AI Price Radar v3.7.8 — Compact Publication Snapshot Hotfix

This patch removes the final refresh bottleneck found while validating v3.7.7 in production.

## What changed

- Builds a compact SQLite publication snapshot containing only `candidates`, `matches`, and `dujiao_candidates`.
- Validates the compact publication artifact instead of reading the full crawler history database twice and copying it once per refresh.
- Keeps the existing crawler database and historical snapshots unchanged.
- Includes the browser request timeout, stale-profile cleanup, bounded teardown, and one-hour inventory budget from v3.7.7.
- Aligns release metadata on `3.7.8`.

## Validation

- Compact publication snapshot test, deployment script tests, crawler tests, API tests, and Web checks must pass before tagging.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.8` Tag after CI succeeds.
- Rebuild the Importer and Crawler images, then complete one full multi-source publication before restoring production timers.
