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
  ├─ reports
  ├─ source_intakes
  └─ notification_outbox
          ↓
FastAPI
          ↓
Next.js
```

人工店铺申请通过 `source_intakes` 状态机进入 `queued`，LDXP crawler 使用独立 Worker Key 领取并回报 `validated`、`no_products` 或 `validation_failed`。只有 `sync_ldxp.py` 在完整快照事务提交后才能回报 `onboarded`。独立 notification worker 消费 Outbox，生产优先使用 Resend API，并保留 SMTP 回退；Merchant JSON Feed 暂留在状态机中，不通过 LDXP 桥接自动收录。

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
