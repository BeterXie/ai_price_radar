# Changelog

All notable changes to AI Price Radar are documented in this file.

## [3.7.20] - 2026-08-27

### Fixed

- Prevented completed LDXP intake attempts from being re-reported on later inventory scans, eliminating false production `409` errors while retaining the metadata required for publication onboarding.
- Made same-attempt scan-result retries idempotent after an intake reaches a closed state; a newer attempt remains rejected as stale.
- Restored LDXP application onboarding after a successful atomic multi-source snapshot, so validated applications with public offers are marked as published.

## [3.7.19] - 2026-08-27

### Fixed

- 16688 discovery now uses the platform's public AI source marketplace to resolve public goods to canonical `/shop/{shop_no}` URLs before the existing detector and review flow.
- Unified source discovery now runs before legacy Dujiao revalidation, and the 16688 and Common Crawl adapters run before the high-volume Bing adapter so Bing cannot consume their discovery opportunity.

## [3.7.17] - 2026-08-27

### Fixed

- Updated Common Crawl discovery regression coverage for the new platform-reserved budget semantics.

## [3.7.16] - 2026-08-27

### Fixed

- Scheduled unified source discovery now obtains its worker key inside the Compose crawler container instead of incorrectly requiring the systemd host service to load the production `.env`.
- Common Crawl discovery reserves candidate capacity for 16688, so high-volume LDXP URLs cannot consume the complete run budget before 16688 shop paths are queried.

## [3.7.15] - 2026-08-27

### Fixed

- The isolated source detector now falls back to another already-validated public DNS address when an initial socket connection fails, allowing 16688 sources to work on IPv4-only egress networks that resolve IPv6 first.
- A successful fallback address is pinned for the rest of the detection run without re-resolving DNS or weakening the existing public-address and TLS hostname checks.

## [3.7.14] - 2026-08-27

### Added

- Added public 16688 shop intake, source detection, approval, atomic publication, and the `16688` connector for public shop and goods APIs.
- Normalized 16688 aliases such as `/shop/HARVEY` to the canonical shop number and scoped shop tokens and product keys by platform so same-named shops do not collide.
- Extended automatic discovery through Bing and Common Crawl for 16688 shop URLs, while keeping discovery auto-approval disabled by default.

### Changed

- Added the v11 database constraint migration for 16688 source intakes and discovery candidates.

## [3.7.13] - 2026-08-22

### Changed

- Refreshed the full Web experience with the Signal Ledger visual system, clearer hierarchy, more consistent typography, responsive layouts, and unified interaction states.
- Reworked public-facing copy to describe observed prices and data freshness more precisely across product, guide, watchlist, submission, policy, and administration surfaces.
- Connected catalog search terms to the public catalog API and preserved available offers when product metadata is incomplete.

## [3.7.12] - 2026-08-22

### Fixed

- Each shop scan now runs inside a supervised browser Worker with a hard wall-clock deadline. A wedged Playwright page or renderer is terminated with its Chromium process group, recorded as a transient failure, and scanning continues with a fresh browser.

## [3.7.11] - 2026-08-20

### Fixed

- The crawler now stores only current matches and run summaries. The unused per-scan `product_snapshots` history no longer grows the operational SQLite database and delays each publication copy.
- Ten-minute inventory refreshes now update only LDXP data while carrying other published sources forward, so a transient external-source timeout cannot block inventory publication.

## [3.7.10] - 2026-08-20

### Fixed

- Compact publication uses a deferred SQLite transaction so the production SQLite runtime does not request a write lock on the attached read-only crawler database.

## [3.7.9] - 2026-08-20

### Fixed

- The compact crawler publication helper now runs on the production host's Python 3.6 runtime.

## [3.7.8] - 2026-08-20

### Fixed

- Scheduled publication now copies only the three current crawler tables used by the publisher instead of validating, copying, and revalidating the full multi-gigabyte history database on every refresh.

## [3.7.7] - 2026-08-20

### Fixed

- Persistent Chromium teardown now stops the Playwright connection directly instead of waiting indefinitely for `BrowserContext.close()` after all shops were scanned.

## [3.7.6] - 2026-08-20

### Fixed

- Browser-replayed shop API requests now abort at the configured crawler timeout instead of allowing one unresponsive source to block every later scan and publication.
- Browser refreshes remove stale Chromium singleton symlinks left by a terminated crawler, and inventory refreshes receive a one-hour service budget so a completed scan can finish atomic publication.
- Release metadata is aligned on `3.7.6` across the API, Web package, lockfile, and repository version marker.

## [3.7.4] - 2026-08-08

### Fixed

- Restored text and icon color utilities on form controls so dark action buttons remain readable.

## [3.7.3] - 2026-08-08

### Changed

- Redesigned the Web pages around a unified product, catalog, offer, guide, and source-review UI system.
- Reworked public copy to distinguish current observations from live data, separate empty and unavailable states, and remove internal workflow wording from user-facing surfaces.
- Clarified watchlist/Atom subscription behavior, correction privacy, offer grouping, information coverage, and source intake outcomes.
- Restored the public author-support entry and kept the existing community prompt wording unchanged.

### Fixed

- Restored support QR configuration defaults for local and production Web builds.
- Updated admin actions and source-discovery labels so buttons describe the action instead of repeating the current state.

## [3.7.2] - 2026-08-06

### Fixed

- LDXP sources in `blocked` or `challenge_required` no longer remain permanently excluded after a transient source-level challenge.
- Blocked sources receive bounded retry times and can be forced immediately with `--retry-blocked`; consecutive source-level failures still stop the scan through the existing circuit breaker.
- Regression coverage now verifies that an all-blocked batch is recorded as failed rather than successful.

### Changed

- Crawler self-tests and pytest coverage now run in CI.

## [3.7.0] - unreleased

### Added

- Unified source discovery engine: seed/Bing/GitHub/Common Crawl adapters submit normalized candidates to a PostgreSQL candidate pool (`source_discovery_runs`, `source_candidates`, v10 migration).
- Source Detector qualification of discovered candidates with bounded public samples and AI product classification, plus strict auto-approval for Dujiao-Next and WooCommerce and manual review for Schema.org and Merchant JSON.
- Internal candidate claim/lease/result APIs, idempotent promotion into `source_intakes`, and admin discovery funnel/controls.
- Production Dujiao discovery now runs GitHub sources with optional token, full AI keywords, and env-driven budgets.

## [3.6.0] - 2026-08-03

### Added

- WooCommerce Store API connector with exact minor-unit pricing, complete pagination validation, and safe variation fallback.
- Schema.org sitemap and product-page JSON-LD connector with bounded discovery and same-origin HTTPS validation.
- Dujiao-Next qualified candidates are auto-approved, and GitHub public repository homepages are a new passive discovery source.
- Source intake, detector, pipeline publication, Web labels, and a v9 database migration for the new source platforms.

### Changed

- Detector platform probing order is now Dujiao-Next, WooCommerce, Merchant JSON, then Schema.org.
- Directly submitted sitemap and product-page URLs are preserved exactly through detection and publication.
- WooCommerce products that are not purchasable never count as in-stock or enter lowest-price comparisons.

## [3.5.0] - 2026-08-03

## [3.5.0] - 2026-08-03

### Added

- Dujiao-Next connector support with brand-aware shop metadata, paginated products, variants, currency preservation, and reviewed-source publication.
- Public-fingerprint discovery with bounded candidate quotas, stale revalidation, isolated platform detection, and administrator-controlled intake routing.
- Merchant JSON intake publication and persistent multi-source refresh across LDXP, Dujiao-Next, and approved merchant feeds.

### Changed

- Complete catalog publication is atomic across all sources and now runs in the dedicated Importer image.
- Intake publication distinguishes raw records, classified offers, and fresh public offers; only a truly visible offer marks a source as published.
- Published sources remain in later complete refreshes, while disabled or review-required sources leave the next snapshot.
- Product brand and source platform are exposed separately across the API and Web application.

### Security

- Detector, Pipeline connectors, and Dujiao discovery share a bounded HTTPS client that pins validated public IPs while preserving TLS SNI and certificate verification.
- Public intake submissions no longer fetch user-controlled URLs inside the API process; the Detector has no database credentials or default-network access.
- Merchant feed shop identity is derived from the canonical feed URL, and public shop/product links reject credentials, fragments, control characters, and non-HTTPS schemes.
- Detector egress is designed for a production firewall policy that permits only public TCP/443 destinations.

## [3.4.0] - 2026-08-02

### Added

- Optional GitHub Star and author-support entry points in the public footer.
- Low-frequency, session-aware community prompts that stay disabled on administrator and shop-submission routes.
- Accessible WeChat Pay and Alipay support dialog with keyboard dismissal and mobile layouts.

### Changed

- Production Web containers can mount support QR images from `data/support` as read-only runtime assets.
- Production preflight validates both public HTTPS QR URLs whenever author support is enabled.

### Security

- Payment QR images and production support configuration remain outside the public Git repository.
- The support dialog does not display or configure a payee name and never records payment information.

## [3.3.1] - 2026-08-02

### Added

- Administrator intake emails now include a direct link to the matching review item in the admin panel.
- Final onboarding emails now include the published public shop page.

### Changed

- Admin intake links still require the administrator key, then scroll to and highlight the referenced request after authentication.

### Security

- Administrator links contain only the intake identifier and never include the administrator key.

## [3.3.0] - 2026-08-02

### Added

- Durable shop-intake records with explicit review, validation, onboarding, rejection, and retry states.
- Admin controls for approving, rejecting, retrying, and inspecting source-intake notification delivery.
- Applicant and administrator email notifications through Resend, with SMTP fallback and a transactional outbox worker.
- LDXP intake bridges for crawler and pipeline jobs, protected by a dedicated worker credential and leased claims.
- Idempotent `migrate_shop_intake_v6.py` migration for historical shop requests and notification outbox storage.

### Changed

- Shop submissions now require a valid contact email and return a stable request identifier for duplicate requests.
- Production preflight now requires administrator recipients, a separate intake-worker key, and a complete Resend or SMTP configuration.
- Production Compose and deployment guidance now include the notification worker and the v6 intake migration.

### Security

- Intake-worker access is isolated from the administrator API key.
- Source validation failures are sanitized before storage or email delivery.
- Resend credentials remain environment-only and are never written to application logs.

## [3.2.1] - 2026-07-30

### Changed

- Rewrote homepage, catalog, product-detail, About, methodology, shop, watchlist, and footer copy in user-facing language.
- Replaced internal pricing and crawler terminology with clearer descriptions such as recent in-stock low, common price, quote coverage, and source update status.
- Simplified grouped-offer labels, anomaly warnings, source links, update timestamps, and product FAQs without changing pricing or ranking behavior.

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
