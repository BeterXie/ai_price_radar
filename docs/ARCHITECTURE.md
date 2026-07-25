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
- Current offers are updated in place.
- Every changed observation is appended to `offer_history`.
- Failed crawler scans do not delete last successful website data.
- An offer becomes stale after 72 hours and stops participating in minimum-price calculations.
- Hidden or unapproved offers remain in the database for audit purposes.
