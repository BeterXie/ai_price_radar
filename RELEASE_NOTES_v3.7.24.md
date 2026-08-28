# AI Price Radar v3.7.24 - Public Catalog and 16688 Classification Fixes

## What changed

- Preserved the flat token-list contract of `GET /api/v1/shops` and added the paginated `GET /api/v1/shops/cards` endpoint for directory pages.
- Excluded hidden products and shops without current public offers from public metadata, source pages, and sitemap entries; added shop-directory pagination.
- Unified API and pipeline 16688 classification with source-category context, rejected non-product aliases, and retained valid API-credit classification.
- Rotated 16688 discovery categories within the global page budget so one category cannot starve the others.

## Safety and data scope

- The 16688 default approval behavior is unchanged. Newly discovered offers still follow the existing approval policy.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.24` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.
- Run one complete multi-source refresh because the release changes crawler and pipeline behavior.
