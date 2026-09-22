# Release Notes - v3.8.1

**发布日期**: 2026-09-23  
**发布版本**: 3.8.1

## 变更概述

v3.8.1 包含异次元/ACG-Faka 开源发卡系统店铺接入支持、邮件通知展示本站收录页面地址以及优惠券彩蛋过期修复：

1. **异次元/ACG-Faka 开源发卡系统店铺接入**：
   - 新增 Connector `pipeline/connectors/acg_faka.py`，支持抓取 `/user/api/index/data` 分类与 `/user/api/index/commodity` 商品列表，自动识别库存、自动发货与价格。
   - 新增探测器 `detector/probe.py` 对 ACG-Faka 系统的探测识别逻辑。
   - 扩展 API 数据模型、模式校验、发现调度，支持 `acg_faka` 平台类型。
   - 管理后台支持审核与重试 `acg_faka` 平台店铺申请。
2. **通知邮件展示店铺在本站收录地址**：
   - 店铺初审通过（`shop_request.approved`）与首次商品上架收录（`shop_intake.onboarded`）的邮件通知正文中，明确展示该店铺同步至本平台的实际访问链接（如 `https://ai.pricememo.cn/shops/acg-faka-f3d199c644dc0ae318539bf3`）。
3. **优惠券彩蛋过期拦截与清理**：
   - 修复优惠券彩蛋触发逻辑：计算剩余库存时过滤已过期的未分配券（`expires_at > now`），待领取且已过期的券不再错误触发彩蛋。
   - 增加登录用户 24 小时领取频控校验，处于冷却期的用户不再触发彩蛋弹窗。
   - 管理后台优惠券列表支持筛选 `expired`（待领取已过期）优惠券，并提供一键批量清理接口 `POST /api/v1/admin/coupons/cleanup-expired`。
4. **数据库结构迁移 (v21)**：
   - 更新 `source_intakes` 与 `source_candidates` 上的检查约束 `ck_source_intakes_type` 与 `ck_source_candidates_platform`，允许 `'acg_faka'` 类型（`scripts/migrate_source_platform_acg_faka_v21.py`）。

## 部署说明

- 生产数据库执行 `scripts/migrate_source_platform_acg_faka_v21.py`。
- 按 `docs/QUICK_DEPLOY.md` 规范构建并部署 `api`、`source-detector`、`importer`、`notification-worker`、`web`。
