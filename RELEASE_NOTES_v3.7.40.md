# AI Price Radar v3.7.40 Release Notes

**Release Date**: 2026-09-05  
**Tag**: `v3.7.40`

---

## Highlights

### 1. 后台商品排序与前台严格对齐（Offer Sorting Alignment）
- 后台报价列表接口 `GET /api/v1/admin/offers` 默认排序改为 `sort="frontend"`，排序规则与前台完全一致：
  1. **有货状态优先**（`in_stock = true` 先于无货商品）
  2. **基准币种优先**（`CNY` 优先排前）
  3. **商品价格低价优先**（`price ASC`）
  4. **最新采集时间优先**（`observed_at DESC`）
- 在管理后台搜索与筛选栏中增加了“排序方式”下拉选择框，支持切换：
  - 前台默认（在售优先 · 低价优先）
  - 最新更新时间优先 (`updated_desc`)
  - 价格从低到高 (`price_asc`)
  - 价格从高到低 (`price_desc`)

### 2. 品牌与分类实时数量徽标与分页加载（Real-time Counts & Pagination）
- 后台统计接口 `GET /api/v1/admin/stats` 增加了 `product_counts`（每个标准产品 slug 的在售公开商品数）和 `brand_counts`（各品牌的在售公开商品数）汇总统计。
- 管理后台的品牌栏（Brand Rail）与产品栏（Product Rail）各按钮实时展示对应的商品数量徽标，方便快速浏览每个分类的具体库存与商品量。
- 后台报价列表新增返回 `X-Total-Count` 响应头，列表上方展示 `共 {offerTotal} 条报价（已载入前 {offers.length} 条）`。
- 列表底部增加“加载更多报价”按钮，当报价超过 100 条时支持分批分页加载，方便完整巡检所有商品。
- 在前后台通用目录 `apps/web/lib/catalog.ts` 的 OpenAI 品牌列表中补齐了 `chatgpt-pro`（ChatGPT Pro）分类选项。

### 3. 执行审批操作不再回滚到页面顶端（Preserve Scroll on Actions）
- 针对用户反馈“后台页面每次执行审批操作以后就又回到了顶端”的问题进行了彻底根治：
  1. **Optimistic In-place Updates**：对批准公开、撤回公开、隐藏限制、恢复公开、重新归类单品等操作改为就地乐观更新 state，避免 React 重新渲染或 unmount 导致焦点重置及浏览器触发平滑回顶滚动。
  2. **`preserveScroll` 滚动坐标保护**：封装滚动位置记录与 `requestAnimationFrame` 即时恢复机制，锁定当前的 `window.scrollY`。
  3. **主动失焦与明确 Button 类型**：在触发操作前对当前焦点元素执行 `blur()`，并明确给全部按钮设置 `type="button"`，杜绝默认表单提交行为。

---

## Verification
- **Backend Tests**: 251 passed (`python -m pytest tests/`).
- **Web Tests**: 55 passed (`node --import tsx --test`).
- **TypeScript Check**: Clean pass with zero errors (`tsc --noEmit`).
