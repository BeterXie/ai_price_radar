# AI Price Radar v3.7.14 — 16688 Source Integration

This release adds end-to-end support for 16688 shops, including automatic discovery of public shops and goods.

## What changed

- Adds 16688 shop intake and platform detection for URLs such as `https://www.16688.com.cn/shop/HARVEY`.
- Resolves public aliases to canonical shop numbers through the 16688 shop detail API.
- Reads public goods through the 16688 goods list API and publishes CNY products through the existing atomic multi-source pipeline.
- Scopes shop tokens (`16688-S343514`) and product keys (`16688:G1`) by platform to avoid collisions with same-named shops elsewhere.
- Extends Bing and Common Crawl discovery to 16688 shop paths; discovered candidates still pass detector validation, AI product checks, and administrator review.
- Keeps `DISCOVERY_16688_AUTO_APPROVE=false` by default.
- Adds the v11 migration for the source platform constraints.

## Validation

- API, Pipeline, Detector, Crawler, migration, and Web checks must pass in CI.
- Production health and public-page smoke checks must report `3.7.14` after deployment.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.14` Tag after CI succeeds.
- This release requires the v11 migration after the existing v10 migration.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`; complete one full multi-source publication before restoring the systemd timers.
