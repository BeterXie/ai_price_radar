# Changelog

All notable changes to AI Price Radar are documented in this file.

## [3.7.39] - 2026-09-05

### Added

- **Admin Category Hierarchy Aligned with Frontend**:
  - Replaced the admin offers panel's flat product slug list with a brand and product rail matching the public catalog (`apps/web/lib/catalog.ts`).
  - Added dedicated navigation views for `🚫 受限/已隐藏` and `❓ 未分类商品` with real-time offer count badges.
  - Added `brand` parameter filtering in `GET /api/v1/admin/offers` and enriched offer responses with `brand` and `product_name`.
  - Added grouped `<optgroup>` selection by brand hierarchy for offer reclassification.
  - Clearly highlighted restriction reasons for restricted/hidden offers with one-click restore (`恢复公开`) and hide (`隐藏/限制`) actions.

### Changed

- **Paused Dujiao-Next Candidate Discovery & Web Submission**:
  - Paused automatic Dujiao-Next discovery in remote refresh scripts (`ENABLE_DUJIAO_DISCOVERY=false`) and removed `dujiao-next` search queries from GitHub discovery.
  - Disabled the Dujiao-Next option on the public shop submission form (`/shops/submit`) with `(暂停收录)` badge.
  - Filtered out `dujiao_next` from the frontend catalog source platform filters.
  - Documented discovery pause and frontend disabled status in `docs/CONNECTORS.md`.

## [3.7.38] - 2026-09-04

### Changed

- **Include Shop Address and Name in Intake Notification Emails**:
  - Added merchant's original shop URL (`店铺地址：{source_url}`) and shop name (`店铺名称：{shop_name}`) to all applicant notification emails:
    - Auto-approval notifications (`shop_request.approved`)
    - Manual approval notifications (`shop_request.approved`)
    - Shop onboarding & publish notifications (`shop_intake.onboarded`), clearly distinguishing the merchant's `店铺地址` and `本站收录页面`
    - Rejection notifications (`shop_request.rejected`)
    - Scan completion with no products (`shop_intake.no_products`) and validation failures (`shop_intake.validation_failed`)
  - Ensures merchants can immediately identify which shop request has been processed and follow the links directly.

## [3.7.37] - 2026-09-04

### Fixed

- **Phone Verification Services Included in Benchmark Comparable Pricing**:
  - Added `verification_service` (`手机接码`, `实卡接码`, `短信验证`) to `COMPARABLE_DELIVERY_TYPES` (`is_comparable=True`).
  - Fixes issue where the dedicated `ChatGPT 手机接码` (`chatgpt-access-service`) product page displayed 0 offers and "暂无有货价" by default because `offerQuery` filters for `comparable=true`.

## [3.7.36] - 2026-09-04

### Changed

- **Reverse-Proxy Tokens Included in Benchmark Pricing**:
  - Included `session_token` delivery type (`只能反代`, `仅反代`, `无账号密码`, `发CDK不可网页`) into `COMPARABLE_DELIVERY_TYPES`.
  - Reverse-proxy token accounts now participate in comparable pricing calculations (`is_comparable=True`) as a recognized account delivery mode.

## [3.7.35] - 2026-09-04

### Fixed

- **Plus Account & SMS Service Precision Classification**:
  - Eliminated false routing into `chatgpt-access-service` caused by substring matching of `接马` inside account status markers (`未接马`, `需自行接马`, `自行接马`, `免接马`).
  - Removed legacy `GENERIC_EMAIL_MARKERS` (Gmail, iCloud) fallback from `chatgpt-access-service`, ensuring accounts with iCloud/Gmail emails (e.g. `韩国-PLUS-icloud邮箱`, `GP Plus gmail越南渠道`) correctly classify as `chatgpt-plus`.
  - Added support for `team` / `周限额` in implicit brand detection so `长效周限额team` routes accurately to `chatgpt-k12`.
  - Enhanced delivery type detection: `未接码`/`未接马` recognized as `semi_finished_account` (半成品/首登号), `icloud` and `保首登` recognized as `finished_account` (成品号).

## [3.7.34] - 2026-09-04

### Changed

- **Codex Classification Merged into ChatGPT Plus & Respective Tiers**:
  - Eliminated the top-level `brand == "codex"` prefix hijacking that forced all Codex-tagged items into `codex-access`.
  - Reclassified Codex accounts into their true underlying tiers: `chatgpt-plus` (for Plus/Sub2API/RT/CPA), `chatgpt-go` (for Codex Go), `chatgpt-k12` (for Team), and `chatgpt-account` (for Free).
  - Preserved `Codex`, `Sub2API`, `带RT` as scenario tags.
- **Dedicated SMS Verification ("手机接码") Category**:
  - Differentiated account attribute markers (`已接码`, `已接马`, `已绑手机`) from independent verification services (`代接码`, `手机接码`, `实卡接码`, `接码卡密`).
  - Allowed SMS verification services through classifier and renamed public frontend tab `辅助服务` to `手机接码`.
  - Removed `Codex` standalone tab from OpenAI navigation header.

## [3.7.33] - 2026-09-04

### Security

- **CRLF & Email Header Injection Protection**:
  - Sanitized `subject`, `recipient`, and `dedupe_key` across the outbox notification pipeline (`apps/api/app/services/source_intake.py` and `apps/api/app/services/outbox.py`).
  - Added strict email format validation in `ShopRequestCreate` forbidding CRLF, control characters, commas, and quotes.
  - Added strict sanitization to `shop_name` and `note` stripping all control characters and angle brackets to prevent header and template injection.
- **SSRF Hardening**:
  - Strengthened `normalize_public_https_url` in `apps/api/app/services/source_platform.py` to forbid internal hostnames, loopback/private/link-local/multicast IPs, and internal TLD suffixes (`.local`, `.internal`, `.lan`, `.home`, `.corp`, `.intranet`, `.priv`, `.arpa`).
  - Verified parameterized SQL queries across all repositories.

## [3.7.32] - 2026-09-04

### Added

- **Automatic Shop Intake Approval**: Enabled automated shop intake approval via `SHOP_INTAKE_AUTO_APPROVE` (`True` in production). When a store request completes automated security and platform detection (`ldxp`, `dujiao_next`, `woocommerce`, `16688`, `merchant_json`, `schema_org`), it is automatically approved into the worker validation/publishing queue without requiring manual admin intervention.
- **Admin Auto-Approval Email Notifications**: Automatically dispatches a notification email (`shop_request.auto_approved.admin`) to configured administrator emails (`SHOP_INTAKE_ADMIN_EMAILS`) whenever a shop request is automatically approved, providing full store details, detected platform, and direct links to the admin console.

### Changed

- **Applicant Notification**: Added explicit notifications to applicants confirming automatic approval upon successful probe detection.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.32` after CI passes.
- Rebuild and restart `api`.
- Set `SHOP_INTAKE_AUTO_APPROVE=true` in `.env` on production.

## [3.7.31] - 2026-09-04

### Added

- **Admin Shop Intake Platform Modification & Manual Approval**: Added platform selection dropdown to the admin console shop intake view (`POST /api/v1/admin/source-intakes/{id}/platform`), allowing administrators to switch an intake's platform type directly (e.g. from `other` to `ldxp`, `dujiao_next`, `16688`, `woocommerce`, `merchant_json`, `schema_org`).
- **On-Demand Platform Re-Detection**: Added `POST /api/v1/admin/source-intakes/{id}/redetect` to re-trigger automatic platform detection for an intake using the latest detection rules.
- **Intelligent Platform Auto-Upgrade on Approval**: Enhanced `POST /api/v1/admin/source-intakes/{id}/approve` to automatically recognize supported platform URLs (such as `wzyp.cn` -> `ldxp`) and approve them directly without throwing 409 errors.

### Fixed

- **Source Detector LDXP Domain Coverage**: Updated `detector/probe.py` to include `wzyp.cn` and `www.wzyp.cn` in `LDXP_HOSTS`, preventing new store applications on `wzyp.cn` (like shop `#37`) from being misclassified as `其他独立站` (`other`).

### Safety and data scope

- No database schema migrations required.
- Existing and future `wzyp.cn` shop intakes can be approved and validated seamlessly.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.31` after CI passes.
- Rebuild `api`, `web`, and `source-detector`.

## [3.7.30] - 2026-09-03

### Fixed

- **Detail-Driven Classification & Brand Detection**: Enabled brand and tier recognition fallback to product detail page descriptions (`raw_products.raw_json->>'description'`) when storefront titles are cryptic or non-standard.
- **Universal Non-Product Exclusion**: Systematically rejected pure tutorials (`教程`, `保姆教程`, `图文教程`, `反代教程`), test items (`测试商品`, `不要拍`, `不可拍`), SMS verification ad services (`接码渠道`), virtual cards (`虚拟卡`, `0刀卡`), and referral boost links from being classified into subscription products.
- **Reverse Proxy / Sub2API Token Isolation**: Offers offering only Sub2API/RT JSON tokens without login credentials (`只能反代`, `无账号密码`) are now correctly classified as `codex-access` (`session_token`) rather than `chatgpt-plus`.
- **ChatGPT Pro Integrity**: Filtered out team bug sub-accounts (`Team bug 子号`) and API quota credits (`20X 额度｜50美金`) from `chatgpt-pro` and `chatgpt-pro-20x`.
- **Multi-User Carpool Isolation**: Expanded `SHARED_POOL_MARKERS` to catch `拼车`, `共享账号`, `多人共享`, and `车位`, ensuring carpool offers are tagged `shared_pool` and `is_comparable = false`, preventing them from distorting individual account comparison prices.
- **Category Group False Positives**: Preserved genuine subscriptions in merchant storefront categories ending in `分组` (e.g. `Grok分组`).

### Safety and data scope

- Synchronized `apps/api/app/services/classifier.py` and `pipeline/common.py`.
- No database schema migrations required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.30` after CI passes.
- Rebuild `api`, `web`, and `importer`.

## [3.7.29] - 2026-09-03

### Added

- Added admin console tabs for reviewing restricted (`status=restricted`) and unclassified (`status=unclassified`) offers, with live count badges on the stats bar.
- Added admin search and target product filter to the offer management table.
- Added support for manual reclassification (including unclassifying back to `None`) and single-offer auto-reclassification via `POST /api/v1/admin/offers/{id}/reclassify`.
- Added visual display of merchant original category and restriction / hidden reasons in the admin offer view.

### Fixed

- Strengthened classifier and pipeline normalization to reject API relay groups (e.g. `plus分组`), relay model channels (e.g. `(cx,5,4)`), and non-20 dollar credit quotas from being falsely classified as `chatgpt-plus`, `chatgpt-pro`, or `codex-access`.

### Safety and data scope

- No schema migrations required.
- Existing restricted offers can now be inspected, audited, and reclassified directly from `/admin`.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.29` after CI passes.
- Rebuild `api`, `web`, and `importer`.

## [3.7.28] - 2026-09-03

### Added

- Added support for `wzyp.cn` and `www.wzyp.cn` storefront hostnames in the `ldxp` platform detector and crawler normalization.
- Added `https://wzyp.cn/shop/KFLA` to public source discovery seeds and crawler candidate database.
- Added `wzyp.cn` guidance to source intake copy in the web application.

### Safety and data scope

- Preserves `token.casefold()` as `source_key` and `token` as `shop_token` under the `ldxp` platform namespace.
- No database migration is required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.28` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.

## [3.7.24] - 2026-08-28

### Fixed

- Preserved the flat token-list contract of `GET /api/v1/shops` and added a paginated shop-card endpoint for directory pages.
- Excluded hidden products and shops without current public offers from public metadata, source pages, and sitemap entries; added pagination for shop directories.
- Unified API and pipeline 16688 classification with source-category context, rejected non-product aliases, and retained valid API-credit classification.
- Rotated 16688 discovery categories within the global page budget so one category cannot starve the others.

### Safety and data scope

- The 16688 default approval behavior is unchanged: newly discovered offers still follow the existing approval policy.
- No database migration is required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.24` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.
- Run one complete multi-source refresh because the release changes crawler and pipeline behavior.

## [3.7.21] - 2026-08-27

### Fixed

- Enforced attempt matching before accepting an idempotent LDXP onboarding response, so a stale onboarding report cannot be mistaken for a retry of the current attempt.

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
