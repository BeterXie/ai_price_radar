# Changelog

All notable changes to AI Price Radar are documented in this file.

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
