# Release Notes v3.7.42

## 变更摘要

- **全站前台禁用 Dujiao-Next**：
  - 在底层公开报价查询（`_base_public_offer_query`）中排除 `dujiao_next` 平台商品，确保全站标准商品详情页、分组聚合页、首页及搜索均不再展示 Dujiao-Next 报价。
  - 在公开店铺接口（`list_public_shops`、`list_public_shop_tokens`、`get_shop_detail`）中排除 `dujiao_next` 店铺，店铺详情对禁用平台直接返回 404。
  - 在 `/api/v1/meta` 中排除 `dujiao_next`，前台平台筛选与总览列表不再出现 Dujiao-Next。
- **前端页面访问阻断**：
  - 访问 `/sources/dujiao_next` 及 `/sources/dujiao_next/products/[slug]` 页面直接触发 `notFound()` 返回 404。
  - 来源平台总览页 `/sources` 过滤掉禁用平台卡片。
- **数据采集发布器排除**：
  - `publish_catalog.py` 从 `approved_intake_sources` 中移除 `dujiao_next`，发布器不再调度抓取 Dujiao-Next。
- **存量数据迁移**：
  - 运行 `scripts/migrate_disable_dujiao_next_v3.7.42.py`，将 `shops` 中 `dujiao_next` 设为不可见，商品标记为已停用隐藏，录入记录设为已停用。
