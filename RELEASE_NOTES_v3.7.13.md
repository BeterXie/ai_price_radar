# AI Price Radar v3.7.13 — Signal Ledger UI

This release refreshes the full website around a clearer, evidence-led product experience.

## What changed

- Applies the Signal Ledger visual system across public pages, guides, tools, submissions, watchlists, product views, and administration.
- Improves color balance, typography, spacing, responsive layouts, navigation, forms, tables, cards, and empty/loading/error/success states.
- Rewrites user-facing copy around observed prices, freshness, data scope, and next actions.
- Connects catalog search terms to the public catalog API.
- Keeps offer results visible when optional product metadata is unavailable.
- Aligns release metadata on `3.7.13`.

## Validation

- API tests, Web type checking, tests, and production build must pass.
- Representative desktop and mobile pages must have no horizontal overflow and key interactive controls must meet the 44px target.
- Production health and public-page smoke checks must report `3.7.13` after deployment.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.13` Tag after CI succeeds.
- This release does not require a database migration or a crawler/pipeline rebuild.
