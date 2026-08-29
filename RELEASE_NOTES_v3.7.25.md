# AI Price Radar v3.7.25 - AI Crawler Readability and Indexing Signals

## What changed

- Added site-wide Organization, WebSite, and SearchAction structured data.
- Added Product and AggregateOffer structured data to product pages.
- Added three distinct HTTPS official evidence anchors to all 22 products and exposed the same evidence in the readable product view.
- Normalized heading hierarchy, contextual internal links, and duplicate listing URL indexing signals without changing the reader-facing information architecture.
- Added optional GA4 AI referral events, an IndexNow key route, and PowerShell submission tooling for IndexNow and Bing Webmaster.
- Wired the new GA4 build-time and IndexNow runtime configuration through the Docker Compose deployment paths.

## Safety and data scope

- No database migration is required.
- No product offers or crawler data are modified by this release.
- GA4 remains opt-in and is disabled when `NEXT_PUBLIC_GA_MEASUREMENT_ID` is empty.

## Validation

- Web typecheck, 55 web tests, production build, Docker Compose configuration, and diff checks passed locally.
- Full CI must pass before tagging and deploying.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.25` after CI passes.
- Rebuild `api`, `web`, and `importer`.
- No full crawler refresh is required for this web/metadata release.
