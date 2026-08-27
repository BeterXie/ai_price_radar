# AI Price Radar v3.7.18 — Public Shop Sitemap Coverage

This release adds public shop pages with current approved offers to the generated sitemap so Google can discover the complete public catalog through one submitted URL.

## What changed

- Added a public API listing visible shop tokens that have fresh, approved offers in the current catalog snapshot.
- Added those shop pages to `sitemap.xml` alongside products and guides.
- Kept filtered query URLs and generated Open Graph images out of the sitemap.

## Validation

- API test suite: 162 passed, 3 skipped.
- Web test suite: 54 passed.
- Web typecheck and production build passed.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.18` tag after CI succeeds.
- No database migration is required.
- Rebuild `api`, `web`, and `importer`; source-detector and crawler images are unchanged.
