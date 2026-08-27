# AI Price Radar v3.7.17 — Verified 16688 Discovery Release

This release packages the scheduled 16688 discovery fix with regression coverage that reflects platform-reserved Common Crawl capacity.

## What changed

- Scheduled unified discovery executes inside the Compose crawler environment, where its worker key is available.
- Common Crawl reserves candidate capacity for 16688 shop paths instead of allowing LDXP paths to consume the entire run budget.
- The crawler test suite verifies both the reserved 16688 capacity and the expected LDXP allocation.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.17` tag after CI succeeds.
- No database migration is required.
- Rebuild the crawler image and deploy the updated scheduler script.
