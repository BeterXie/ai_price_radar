# Release Notes - v3.9.3

**发布日期**: 2026-09-25
**发布版本**: 3.9.3

## 变更概述

- 链动小铺浏览器扫描成功时，将公开店铺介绍、公告和规则保存到爬虫 SQLite 的 `candidates.shop_notice`，记录采集时间；暂时失败时保留上次成功采集的介绍。
- 独立店铺同步脚本可只读获取这些介绍，提取对接码并验证私域商品。该脚本独立部署，不包含在本仓库发布包中。

## 部署说明

- 无 PostgreSQL 迁移；爬虫启动时自动补齐 SQLite 的 `shop_notice` 和 `notice_observed_at` 列。
- 按 `docs/QUICK_DEPLOY.md` 发布同一 Tag 的 API、Web、来源检测、Importer 和 Crawler；本次修改 `crawler/`，必须重建 Crawler 并完成一次完整刷新。
- 爬虫重新扫描店铺后，独立同步脚本才能读取新增的介绍文本。
