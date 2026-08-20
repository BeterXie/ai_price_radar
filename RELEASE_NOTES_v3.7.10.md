# AI Price Radar v3.7.10 — Read-Only Snapshot Transaction Hotfix

This patch completes compatibility with the production host's Python 3.6 and SQLite runtime.

## What changed

- Uses a deferred transaction while copying the attached read-only crawler database into the compact publication database.
- Verifies the helper against an explicitly read-only source database.
- Retains all crawler request, profile cleanup, teardown, and compact publication fixes from v3.7.9.
- Aligns release metadata on `3.7.10`.

## Validation

- Compact publication tests must pass with a read-only source.
- The helper must run successfully with production Python 3.6 before publication.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.10` Tag after CI succeeds.
