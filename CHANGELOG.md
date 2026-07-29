# Changelog

All notable changes to AI Price Radar are documented in this file.

## [3.2.0] - 2026-07-29

### Added

- Official price references, verification dates, product data-quality scores, source scan-health facts, and daily aggregated price/stock trends.
- Browser-local watchlists and privacy-preserving Atom price/restock subscriptions.
- Public methodology, privacy, terms, security, developer, and correction-log pages.
- Public correction summaries with optional merchant responses while keeping reporter contacts private.
- Generic connector protocol, merchant HTTPS JSON Feed importer, submission flow, fixtures, and tests.
- Full delivery, period, warranty, fulfillment, freshness, stock, and price-range filters across catalog and product pages.

### Changed

- Default catalog ranking now prioritizes data quality and freshness before price.
- Homepage and directory counters use one published-snapshot scope and show trusted/comparable context.
- Price history presentation uses daily aggregates instead of connecting unrelated raw observations.
- Source-health labels explicitly describe crawler availability rather than merchant reputation.

### Security

- Merchant Feed submissions require public HTTPS URLs and reject localhost, internal hostnames, and private/reserved IP literals.
- Public correction endpoints exclude raw report messages and contact information.

## [3.1.0] - 2026-07-29

### Added

- Trusted-price scoring derived from comparable inventory and delivery-type medians.
- `trusted_offer_count` and `median_price` in public product responses.
- Per-offer `is_trusted_price` indicator while retaining anomaly warnings.
- API pricing unit tests and GitHub Actions checks for API and Web builds.
- Version, security, contribution, and release documentation.

### Changed

- Product cards and product details now use the trusted lowest price as the primary price.
- Extremely low or strongly off-median offers remain visible as source evidence but no longer lead the primary ranking.
- Related/all-in-stock lowest price remains available through `related_lowest_price` for backward compatibility.
- Homepage copy now distinguishes trustworthy rankings from raw low prices.
- Product structured data reports trusted offers rather than every comparable offer.

### Fixed

- Prevented ¥0.01 promotion, balance, trial, or restricted offers from becoming the headline price.
- Prevented anomalous representatives from being selected ahead of trustworthy offers inside grouped results.

## [3.0.0]

- Initial public architecture with FastAPI, Next.js, snapshots, classification, grouping, and price history.
