# AI Price Radar v3.5.0 — Multi-Source Discovery

This release expands the catalog from one shop ecosystem to reviewed Dujiao-Next and Merchant JSON sources, while tightening the network and publication boundaries around externally supplied data.

## What changed

- Added Dujiao-Next shop discovery, API verification, brand-aware metadata, product pagination, variants, and original-currency publication.
- Added asynchronous source intake detection and source-specific routing for LDXP, Dujiao-Next, Merchant JSON, and manual sources.
- Publish all enabled sources into one atomic catalog snapshot; any connector failure preserves the previous published snapshot.
- Continue refreshing approved and previously published sources, while removing disabled sources from subsequent snapshots.
- Report raw, classified, and fresh public-offer counts separately; only a source that produces a currently visible offer becomes `published`.
- Separate product brand from source platform throughout the API and Web catalog.

## Security

- Public submissions are stored without fetching the submitted URL in the API process.
- The isolated Detector has a dedicated credential and no database, Redis, Docker socket, or default-network access.
- Detector, Pipeline connectors, and Dujiao discovery use a shared fixed-IP HTTPS client with complete DNS-answer validation, TLS SNI and certificate checks, HTTPS 443 only, no redirects, and bounded response/time budgets.
- Merchant JSON shop identities are derived from canonical feed URLs; upstream tokens cannot overwrite an existing shop.
- Merchant shop and product links reject credentials, fragments, control characters, private literals, and non-HTTPS schemes.
- Production must enforce Detector egress with a firewall or proxy that permits only public TCP/443 destinations.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` without reordering migration or switch steps.
- Rehearse and then run the idempotent v5, v6, v7, and v8 migrations before switching the new API.
- Build API, source-detector, Web, Importer, and Crawler images from this Tag; `shared_http` must be identical in Detector, Importer, and Crawler.
- Run complete catalog publication with `ai-price-radar-importer`, not the API image.
- Because this release changes crawler, pipeline, and database behavior, one successful complete multi-source refresh is a deployment gate.

## Compatibility

- Existing LDXP sources remain supported.
- `merchant_feed` remains accepted only as an API input alias and is persisted as `merchant_json`.
- Legacy brand and source-platform query aliases remain available for existing clients.
- Existing v5-v8 migrations are idempotent and are expected to be safe to run again during deployment.
