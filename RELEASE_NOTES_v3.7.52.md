# Release Notes v3.7.52

## 变更摘要

- **卡片外层展示最低价对齐**：
  - 优化同款聚合卡片（`OfferGroupPublic`）的外层价格计算逻辑：优先取同款账号中有货的最低报价（全缺货时回退取全体最低价），确保外层右上角观测价与选出的代表商品（最低价有货店铺）标价完全一致。
- **内层店铺报价纯升序排列**：
  - 后端 `get_group_offers` 针对组内同款报价调整排序为价格升序（`Offer.price.asc()`），价格相同时优先有货。
  - 前端 `ShopOfferList` 组件增加保底排序，确保展开后所有店铺报价严格按价格由低到高呈现（如 `¥20.00 -> ¥22.00 -> ¥23.00 -> ¥23.50 -> ¥30.00`）。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.52`。

## 验证

- `apps/api/tests/test_catalog.py` 新增 `test_group_lowest_price_matches_lowest_in_stock_and_group_offers_sorted_by_price_asc` 测试用例，后端 330 项测试全部通过。
- `apps/web` TypeScript 类型检查通过，60 项测试全部通过。
