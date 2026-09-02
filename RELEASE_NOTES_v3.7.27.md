# AI Price Radar v3.7.27 - Deferred Product History and Atom Feed Documentation

## What changed

- Removed history and 90-day trend aggregation from the default product-detail response; the chart now loads from a dedicated history endpoint near the viewport.
- Added a product-detail loading boundary and a lazy history panel so high-volume products can render their current offers without waiting for historical data.
- Documented the required `targets` query for the public Atom feed and exposed the same contract in the API parameter description.

## Safety and data scope

- The default detail response still uses the current published offer data and does not change pricing or stock calculations.
- No database migration is required, and no offer or crawler data is modified.

## Validation

- API tests, Web TypeScript typecheck, and the production build must pass before release.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.27` after CI passes.
- Rebuild `api`, `web`, and `importer`.
- No full crawler refresh or database migration is required for this API/Web release.
