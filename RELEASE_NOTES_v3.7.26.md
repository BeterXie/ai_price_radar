# AI Price Radar v3.7.26 - Crawl Resilience and Shop Product Discovery

## What changed

- Made dynamic sitemap sources fail independently so a temporary catalog, shop, metadata, or source-platform API failure does not remove unrelated URLs from the sitemap.
- Added current standard-product summaries to shop detail API responses and linked each shop page to its stable product pages.
- Added an `ItemList` describing the shop's related standard products for search crawlers.

## Safety and data scope

- Shop products are derived only from visible, approved, active, fresh offers in the current published snapshot.
- No database migration is required, and no offer or crawler data is modified.

## Validation

- API tests, Web tests, TypeScript typecheck, production build, and production client URL checks passed locally.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.26` after CI passes.
- Rebuild `api`, `web`, and `importer`.
- No full crawler refresh is required for this API/Web metadata release.
