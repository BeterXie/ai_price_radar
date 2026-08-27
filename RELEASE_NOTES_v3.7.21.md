# AI Price Radar v3.7.21 - Strict LDXP Onboarding Attempts

## What changed

- LDXP onboarding retries are idempotent only when they carry the current intake attempt number.
- A stale onboarding report is rejected with HTTP 409 before any terminal-state shortcut is applied.

## Validation

- API coverage verifies that a repeated onboarding report for the same attempt succeeds and a different attempt is rejected.

## Deployment

- No database migration is required. Rebuild and switch the API, Web, importer, and crawler from the `v3.7.21` tag, then run one complete refresh before restoring timers.
