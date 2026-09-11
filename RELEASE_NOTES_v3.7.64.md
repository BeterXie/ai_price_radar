# Release Notes v3.7.64 - 根治爬虫调度饥饿与增量快照失效商品滞留问题

**Release Date:** 2026-09-11  
**Version:** 3.7.64  

---

## 变更概要 (Overview)

本版本根治了生产环境报价刷新后下架商品未及时剔除与低分店铺长期无法巡检的问题：
1. 爬虫调度器引入公平轮转（Fair Round-Robin）机制，彻底消除高分店铺垄断导致的低分店铺“饥饿”现象；
2. 增量快照同步引入受触店铺失效商品清理机制，确保原站已下架的商品能被精准移出最新快照并标记为下架。

---

## 主要更新点 (Key Updates)

1. **爬虫公平调度算法 (`crawler/ldxp/ldxp_crawler/db.py`)**
   - 优化 `list_candidates` 排序策略：
     - 在 `matched_only=True`（存量库存巡检）模式下，已尝试过的店铺优先按 `last_attempt_at ASC`（最久未扫描优先）轮转，不再受 `source_score DESC` 绝对压制，保证 128 家存量店铺在有限轮次内 100% 均匀覆盖；
     - 在 `rescan=True` 全量重扫模式下，已尝试过的店铺同样按 `last_attempt_at ASC` 轮转；
     - 新提报未扫描的店铺依然保持最高优先级插队。

2. **增量快照下架清理 (`pipeline/publish_catalog.py`, `pipeline/sync_source.py`)**
   - 新增 `_prune_stale_offers` 机制：在 `carry_forward_current=True` 增量发布时，针对本次导入涉及到的所有店铺（Touched Shops），若存在继承自旧快照但已不在本次来源数据中的 Offer，将其从最新快照彻底移出（`snapshot_id = None`）并将 `stock_status` 更新为 `unavailable`。
   - `sync_source.py` 摘要中新增 `pruned` 计数输出，便于观测每次增量同步剔除的失效报价数量。

3. **单元测试与回归防护**
   - 新增 `crawler/ldxp/tests/test_fair_scheduler.py`，验证低分店铺不会被高分店铺饿死。
   - 在 `pipeline/tests/test_publish_catalog.py` 中新增 `test_carry_forward_prunes_stale_offers_for_touched_shops`，验证失效商品下架清理与未改动店铺的平稳继承。
