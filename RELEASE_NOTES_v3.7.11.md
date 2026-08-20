# AI Price Radar v3.7.11 — Compact Crawler State

This patch removes an unused local crawler history path that inflated the production SQLite database to multiple gigabytes and made scheduled publication slower than its interval.

## What changed

- Stops creating and writing `product_snapshots`; PostgreSQL remains the source of public offer history.
- Keeps the crawler's current candidates, matches, run summaries, and reviewed Dujiao candidates.
- Uses the incremental carry-forward publisher for 10-minute LDXP inventory refreshes; hourly refreshes remain authoritative multi-source transactions.
- Aligns release metadata on `3.7.11`.

## Validation

- Crawler tests must confirm that successful scans still replace current matches without creating `product_snapshots`.
- Compact publication tests and production preflight must pass.
- Inventory entrypoint tests must confirm that external-source availability no longer gates LDXP-only refreshes.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.11` Tag after CI succeeds.
- With all crawler timers stopped, replace the existing crawler SQLite file atomically with a validated compact copy that contains `candidates`, `matches`, `scan_runs`, and `dujiao_candidates`. Preserve the old file as the existing deployment rollback artifact.
