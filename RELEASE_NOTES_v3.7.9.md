# AI Price Radar v3.7.9 — Production Python Compatibility Hotfix

This patch makes the compact publication helper compatible with the production host's Python 3.6 runtime.

## What changed

- Replaced Python 3.9 built-in generic annotations with `typing.Dict`.
- Replaced the Python 3.8 `Path.unlink(missing_ok=...)` form with an explicit existence check.
- Retains the compact publication snapshot and crawler stall fixes from v3.7.8.
- Aligns release metadata on `3.7.9`.

## Validation

- Compact publication snapshot and production-syntax tests must pass before tagging.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.9` Tag after CI succeeds.
- Run the helper with production Python 3.6 before switching the publication path.
