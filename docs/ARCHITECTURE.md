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

公开店铺申请只校验 HTTPS URL 语法并以 `submitted` 保存，不在 API 请求进程中访问用户控制的地址。独立 `source-detector` 使用专用 Worker Key 领取任务，在受限网络中完成来源识别后回报 `pending_review` 或 `validation_failed`。Detector 不持有数据库、Redis 或 Docker API 凭据，也不加入默认数据库网络。

管理员批准后按来源分流：LDXP 进入 `queued`，由 LDXP crawler 使用独立 Intake Worker Key 领取和验证；Dujiao-Next、Merchant JSON、WooCommerce、Schema.org 和 16688 进入 `approved`，由统一发布器消费；`other` 保持人工接入。Dujiao/Merchant/WooCommerce/Schema.org/16688 只有在新快照中至少产生一个真实公开报价时才从 `approved` 变为 `published`；`published` 来源会持续参加后续完整刷新，直到被禁用或要求复审。任一技术失败会回滚整个草稿。独立 notification worker 消费 Outbox，生产优先使用 Resend API，并保留 SMTP 回退。

16688 的 `HARVEY` 等公开路径别名会在检测和发布时解析为真实店铺号，并归一化为 `/shop/{shop_no}`。发布器为其生成带平台前缀的店铺 token（例如 `16688-S343514`）和商品键（例如 `16688:G1`），因此同名店铺或相同编号不会跨平台覆盖。

Dujiao-Next 自动发现使用隔离的 crawler SQLite `dujiao_candidates` 表：seed/Bing 公开命中经过 HTTPS/SSRF 检查、受限响应读取、公开 API 契约和 AI 商品验证后进入本地 `pending_review`。人工批准或拒绝只改变审核元数据，不创建 Shop、Offer 或 Snapshot。统一发布器只读取仍然 API 有效的 approved 发现候选和已批准人工申请，并与 LDXP、Merchant JSON 一起写入同一个待发布快照。

## Publication guarantees

- Import is idempotent by `shop token + source product key`.
- Current offers are updated in place and assigned to one multi-source catalog snapshot.
- All configured sources publish in the same transaction; any source failure rolls back the draft and preserves the previous complete snapshot.
- Discovery and approval do not publish data; only the reviewed-source publisher can switch the public snapshot.
- Approved and published intake sources are both authoritative refresh inputs; publishing a snapshot never silently drops a still-enabled source.
- Intake publication counts raw records, classified offers and public offers separately; only a positive public-offer count marks the intake published.
- Public pages only read the latest published snapshot.
- Standard-product identity is separate from delivery form and price comparability.
- Cross-shop duplicates are grouped by a normalized item fingerprint at read time.
- Every changed observation is appended to `offer_history`.
- Failed crawler scans do not delete last successful website data.
- An offer becomes stale after 72 hours and stops participating in minimum-price calculations.
- Hidden or unapproved offers remain in the database for audit purposes.
