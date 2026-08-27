# AI Price Radar v3.7.19 - 16688 Public Source Discovery

This release fixes 16688 shop discovery when Bing and Common Crawl have no usable indexed shop pages.

## What changed

- Added a bounded `16688` discovery adapter that reads the public `AI与效率` source marketplace, resolves each public goods number through the public goods-detail API, and submits only the resulting official `/shop/{shop_no}` URL.
- Kept the existing candidate detector, administrator review, and atomic publication path unchanged. Discovered 16688 shops remain pending review by default.
- Ran unified source discovery before legacy Dujiao revalidation and before high-volume Bing collection.

## Validation

- Focused crawler, API, and scheduler tests cover the official goods-to-shop resolution, adapter acceptance, and execution order.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.19` tag after CI succeeds. Existing production `.env` files must add `16688` to `DISCOVERY_SOURCES`.
- Rebuild `api`, `web`, `crawler`, and `importer`; no schema migration is required.
