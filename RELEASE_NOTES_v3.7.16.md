# AI Price Radar v3.7.16 — 16688 Discovery Scheduler Fix

This patch makes scheduled 16688 discovery execute in production and prevents Common Crawl capacity from being monopolized by another storefront platform.

## What changed

- The scheduled discovery script always invokes unified source discovery. The crawler receives `DISCOVERY_WORKER_KEY` from Docker Compose, without exposing the production `.env` to the systemd host service.
- Common Crawl reserves discovery capacity by storefront platform, including both apex and `www` 16688 shop URL patterns.
- Bing remains a supplemental source only. A live browser check found no Bing-indexed 16688 shop pages for either the current AI query or the general shop-path query.

## Impact

- Scheduled runs can create and qualify new 16688 source candidates.
- Discovered 16688 shops still require administrator review before publication; automatic approval remains disabled.

## Validation

- Crawler regression coverage verifies that 16688 URLs are still collected when LDXP fills its own Common Crawl allocation.
- Follow the production runbook and verify a scheduled or manual discovery run creates a new `source_discovery_runs` record.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.16` tag after CI succeeds.
- No database migration is required.
- Rebuild the crawler image and deploy the updated scheduler script; standard release gates still apply.
