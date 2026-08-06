# AI Price Radar v3.7.2 — LDXP Blocked-Source Recovery

This hotfix restores periodic updates for LDXP sources that were left in a permanent `blocked` state after the v3.7.1 crawler rollback.

## What changed

- Retry `blocked` sources after a 6-hour backoff and `challenge_required` sources after a 24-hour backoff.
- Keep `--retry-blocked` as an explicit operator override that ignores the remaining backoff window.
- Preserve the existing three-source circuit breaker so a site-wide challenge stops a scheduled batch quickly.
- Verify that blocked scans count as failures and never satisfy the successful-scan publication gate.
- Run the crawler self-test and pytest suite in CI.

## Deployment

- No database migration is required.
- Follow `docs/QUICK_DEPLOY.md` and rebuild the Crawler image from this Tag.
- Because this release changes crawler behavior, complete one successful multi-source refresh before restoring all production timers.
- Existing blocked rows with no retry timestamp become immediately eligible in bounded batches; successful scans reset their failure state normally.
