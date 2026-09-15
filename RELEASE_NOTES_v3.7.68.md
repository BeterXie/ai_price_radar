# AI Price Radar v3.7.68 — Smooth Tab Navigation & Snapshot Catalog Integration

## 概述

本版本重点解决了商品详情/分类页面在切换不同商品类型（如 ChatGPT Plus、Pro 5x 等）时的骨架屏白屏闪烁问题，实现了毫秒级无感就地平滑切换；同时接入了面向 LLM 与自动化工具的不可变只读数据快照规范与公共数据接口，提升了高并发场景下的首屏渲染性能。

## 变更明细

1. **商品类型切换无感过渡 (Smooth Tab Transition)**:
   - 彻底移除 `apps/web/app/products/[slug]/loading.tsx`，消除 Next.js App Router 在同一动态路由段跳转时强制卸载页面造成的骨架屏与白屏闪烁。
   - 分类 Tab 与平台 Filter 链接注入 `prefetch={true}`，并在服务端开启 30 秒客户端缓存（`revalidate = 30`），在用户点击前预取完毕。
   - 使用 React `cache()` 消除元数据生成与页面组件渲染时的重复接口调用。

2. **不可变只读快照与开发者接口规范**:
   - 提供公共 Feed 路由 `/api/v1/feed` 以及面向大模型的全站说明文档 `/price-radar-api.md`、`/.well-known/price-radar.json` 和 JSON Schema `/price-radar-v1.schema.json`。
   - 数据发布管道（`pipeline/publish_catalog.py`）发布完成后自动生成最新只读不可变快照（`pipeline/export_snapshot.py`）。
   - 前端支持从不可变快照直接读取渲染商品列表，降低对数据库实时查询的依赖。

3. **API 超时与构建稳定性**:
   - `apiFetch` 增加超时中断与取消信号，避免并发静态生成或网络波动时请求挂起。

## 生产部署说明

- 本次改动涉及 `apps/api`、`apps/web` 与 `pipeline/`，不涉及数据库迁移。
- 遵循 `docs/QUICK_DEPLOY.md` 标准发布流程重建 `api`、`web` 与 `importer` 容器。
