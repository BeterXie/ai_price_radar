# AI Price Radar v3.1.0 — Trusted Pricing

This release changes the primary catalog signal from “lowest comparable price” to “lowest trustworthy comparable price.”

## Highlights

- Prices below ¥1 are kept for traceability but excluded from the headline price.
- Prices below 40% of the median for the same delivery type are flagged for review and excluded from trusted ranking.
- The API exposes trusted-offer counts and median prices without removing existing fields.
- Product cards clearly distinguish trusted prices from the lowest price among all in-stock related offers.
- CI validates the FastAPI test suite, TypeScript types, and the production Next.js build.

## Compatibility

- `lowest_price` now represents the trusted lowest price.
- `related_lowest_price` continues to represent the lowest price across all in-stock related offers.
- Existing clients remain structurally compatible; new response fields are additive.
- No database migration is required.

## Validation

Before tagging, complete the automated API tests, TypeScript check, production Web build, and the staging checks in `docs/RELEASE_CHECKLIST.md`. No database migration is required.

After validation, tag the commit as `v3.1.0` and use this file as the GitHub Release description.
