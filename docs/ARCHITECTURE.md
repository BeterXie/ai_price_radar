# Architecture

```text
Public indexes / seed URLs
          ↓
LDXP crawler + Dujiao public-API discovery
          ↓
ldxp_crawler.db (offers + isolated review candidates)
          ↓
human review + configured Merchant Feeds
          ↓
publish_catalog.py (one draft snapshot)
          ↓
connectors + normalizer + classifier
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

Dujiao-Next 自动发现使用隔离的 crawler SQLite `dujiao_candidates` 表：seed/Bing 公开命中经过 HTTPS/SSRF 检查、受限响应读取、公开 API 契约和 AI 商品验证后进入本地 `pending_review`。人工批准或拒绝只改变审核元数据，不创建 Shop、Offer 或 Snapshot。统一发布器只读取仍然 API 有效的 approved 候选，并与 LDXP、配置的 Merchant Feed 一起写入同一个待发布快照。

## Publication guarantees

- Import is idempotent by `shop token + source product key`.
- Current offers are updated in place and assigned to one multi-source catalog snapshot.
- All configured sources publish in the same transaction; any source failure rolls back the draft and preserves the previous complete snapshot.
- Discovery and approval do not publish data; only the reviewed-source publisher can switch the public snapshot.
- Public pages only read the latest published snapshot.
- Standard-product identity is separate from delivery form and price comparability.
- Cross-shop duplicates are grouped by a normalized item fingerprint at read time.
- Every changed observation is appended to `offer_history`.
- Failed crawler scans do not delete last successful website data.
- An offer becomes stale after 72 hours and stops participating in minimum-price calculations.
- Hidden or unapproved offers remain in the database for audit purposes.
