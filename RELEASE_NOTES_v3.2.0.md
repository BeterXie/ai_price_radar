# AI Price Radar v3.2.0 — Productization & Evidence

This release turns the trusted-pricing foundation into a more complete public data product.

## Highlights

- Official list-price references with source links and verification dates for supported flagship plans.
- Product data-quality scores and factual source scan-health indicators.
- Daily aggregated trusted-lowest, median-price and in-stock trend data.
- Browser-local watchlists plus privacy-preserving Atom price/restock feeds.
- Complete offer filters across catalog and product pages.
- Public methodology, privacy, terms, security, developer and correction-log pages.
- Public correction summaries and optional merchant responses, without exposing private contact data.
- Generic source connector interface and merchant HTTPS JSON Feed support.
- Merchant Feed submissions alongside LDXP shop submissions.

## API additions

- Expanded product/catalog metrics: trusted, comparable and in-stock counts under one snapshot scope.
- `official_reference`, `data_quality_score`, `source_count`, `source_health` and `trend` fields.
- `GET /api/v1/corrections`.
- `GET /api/v1/watch.atom?targets=slug:target_price`.

## Upgrade

1. Back up PostgreSQL.
2. Run the existing v4 migration when upgrading from a pre-3.1 database.
3. Run `python scripts/migrate_productization_v5.py --database-url "$DATABASE_URL"`.
4. Deploy API and Web together because public response types have expanded.
5. Run API, pipeline and Web release gates before tagging.

No existing offer or history data is deleted.
