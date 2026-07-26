# Architecture

```text
Public indexes / seed URLs
          ↓
LDXP browser crawler
          ↓
ldxp_crawler.db
          ↓
sync_ldxp.py
          ↓
normalizer + classifier
          ↓
PostgreSQL
  ├─ shops
  ├─ raw_products
  ├─ products
  ├─ offers
  ├─ catalog_snapshots
  ├─ offer_history
  ├─ scan_runs
  └─ reports
          ↓
FastAPI
          ↓
Next.js
```

## Publication guarantees

- Import is idempotent by `shop token + source product key`.
- Current offers are updated in place and assigned to a new catalog snapshot.
- A complete import publishes its snapshot in the same transaction; partial imports roll back.
- Public pages only read the latest published snapshot.
- Standard-product identity is separate from delivery form and price comparability.
- Cross-shop duplicates are grouped by a normalized item fingerprint at read time.
- Every changed observation is appended to `offer_history`.
- Failed crawler scans do not delete last successful website data.
- An offer becomes stale after 72 hours and stops participating in minimum-price calculations.
- Hidden or unapproved offers remain in the database for audit purposes.
