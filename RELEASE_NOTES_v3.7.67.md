# AI Price Radar v3.7.67 — AI Price Memory Brand Alignment & SSR Resilience

## 概述

本版本将全站网页可见文案统一升级为 `AI Price Memory`，并在所有 SEO 元数据与结构化数据中全面融入新旧双品牌支持。同时增强了 Next.js 前端调用内部 API 时的网络异常重试机制，解决 Docker 内部 DNS 抖动导致的 SSR 渲染偶发报错问题。

## 变更明细

1. **品牌文案统一升级**:
   - 网页可见文案（页脚 `AI Price Memory 开源项目`、关于页 `关于 AI Price Memory`、商业合作推广页、数据来源与详情页说明、全站购买指南与工作流免责声明、支持弹窗文案等）全部更新为 `AI Price Memory`。
   - 保留开源仓库链接 `https://github.com/BeterXie/ai_price_radar` 不变。

2. **SEO 与搜索引擎双品牌兼容**:
   - 全局标题模板、OpenGraph 站点名（`AI Price Memory / AI Price Radar`）、页面描述均追加新品牌词。
   - Schema.org 结构化数据：Organization 与 WebSite 主名称设为 `AI Price Memory`，`alternateName` 包含 `AI Price Radar` 与 `PriceMemo`，平滑承接历史搜索流量。

3. **SSR API 调用重试容灾**:
   - 为前端 `apiFetch` 增加指数退避重试，有效抵御内网 DNS 解析偶发 `EAI_AGAIN` 等网络瞬态故障。

## 生产部署说明

- 本次改动涉及 `apps/web` 与 API 版本号；不涉及数据库迁移与爬虫改动。
- 遵循 `docs/QUICK_DEPLOY.md` 标准发布流程重建 `api` 与 `web` 容器。
