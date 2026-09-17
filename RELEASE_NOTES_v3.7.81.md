# Release Notes - v3.7.81

## 商品外链点击统计与店铺访问量看板 (v3.7.81)

**发布日期**: 2026-09-17  
**核心目标**: 满足商家与用户对商品热度与商户点击率的反馈需求，精准沉淀商品外链（访问原站）点击量，并在商品卡片与商家主页提供实时数据看板。

---

### 一、核心功能特性

1. **商品访问热度沉淀与极速读取**
   - 在 `offers` 表新增 `click_count` 计数字段，列表与详情页面支持毫秒级 $O(1)$ 读取展示；
   - 新增 `offer_clicks` 明细表记录每次点击的时序事件（商铺、商品、IP 哈希、User-Agent 与时间戳）；
   - 前端商品卡片和全部店铺报价表格中直观展示访问热度徽章（例如：`🔥 128 次访问`）。

2. **短时间防刷与防重机制**
   - 后端提供 `/api/v1/offers/{offer_id}/click` 上报接口，内置 60 秒 IP 哈希防刷去重；
   - 相同客户端 IP 在 60 秒内连续点击同一商品外链时，自动返回当前真实计数值而不重复增加计数，杜绝恶意脚本刷榜或手抖连击。

3. **异步无感保活上报**
   - 前端点击“查看原站”或“去原站查看”时，采用原生 `fetch(..., { method: 'POST', keepalive: true })` 技术；
   - 保证用户在新标签页打开外部店铺时，上报请求在后台可靠完成，绝不阻塞用户跳转体验。

4. **店铺主页访问量专属看板**
   - 在店铺主页（`/shops/[token]`）显著位置展示商家专属看板：
     - **当日商品点击数**（以北京时间当天 00:00:00 起算）；
     - **累计总点击数**；
   - 为“访问原店铺”按钮封装专属组件 `ShopVisitButton`，同步上报商铺主页点击事件。

---

### 二、技术升级清单

- **数据库迁移**: `scripts/migrate_offer_clicks_v17.py`
- **数据模型**: `Offer.click_count`, `OfferClick`
- **数据契约**: `OfferPublic.click_count`, `OfferGroupPublic.click_count`, `ShopDetail.today_clicks`, `ShopDetail.total_clicks`, `OfferClickResponse`
- **业务逻辑与路由**:
  - `apps/api/app/services/catalog.py`: 聚合计算 `today_clicks`（UTC+8 CST）与 `total_clicks`
  - `apps/api/app/routers/public.py`: 暴露 `/offers/{offer_id}/click` 与 `/shops/{token}/click`
- **前端组件**:
  - `apps/web/components/offer-table.tsx`: 热度标签与 `trackOfferClick` 保活上报
  - `apps/web/components/shop-visit-button.tsx`: 客户端商铺点击上报组件
  - `apps/web/app/shops/[token]/page.tsx`: 增加今日/累计点击统计徽章
- **自动化测试**:
  - `apps/api/tests/test_offer_clicks.py` (5 个用例全部通过)
  - 全量 pytest 376 passed
  - 前端 test 63 passed, TypeScript 0 errors
