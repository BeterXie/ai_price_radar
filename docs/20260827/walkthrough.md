# 优化成果汇总：16688 检索与 SEO 架构升级

基于 `docs/20260827/` 下的两份交接文档（`16688_store_search_handoff_project_based.md` 和 `ai_pricememo_seo_search_optimization_handoff_project_based.md`），已完成对 `BeterXie/ai_price_radar` 的全量优化。

---

## 1. 16688 Discovery 召回率优化

### 关键词覆盖扩充 (`keywords.py`)
修改了 [keywords.py](file:///C:/Users/59908/ai_price_radar_v3/crawler/ldxp/ldxp_crawler/source_discovery/keywords.py) 中的 `bing_16688_queries()`：
- 覆盖高价值核心品牌词：`ChatGPT`, `Codex`, `OpenAI`, `Claude`, `Gemini`, `Grok`
- 覆盖细分套餐词：`ChatGPT Plus`, `ChatGPT Pro`, `SuperGrok`, `Claude Pro`, `Gemini Advanced`, `OpenAI API`
- 覆盖服务与接码关键词：`Codex 接码`, `接码`, `验证码`, `成品号`
- 确保所有查询限定在 `site:16688.com.cn/shop`，并避免笛卡尔积爆炸以控制 Bing RSS 查询预算。

### 自动化单元测试 (`test_source_discovery.py`)
在 [test_source_discovery.py](file:///C:/Users/59908/ai_price_radar_v3/crawler/ldxp/tests/test_source_discovery.py) 中新增了 `test_bing_16688_queries_coverage()` 测试：
- 断言查询包含 Codex、接码、验证码、成品号及主流模型品牌词。
- 断言查询无重复且全部限定在 16688 官方域名。

---

## 2. 后端 API 升级与服务扩展

### Schema 新增 (`schemas.py`)
在 [schemas.py](file:///C:/Users/59908/ai_price_radar_v3/apps/api/app/schemas.py) 中新增：
- `ShopCard`：包含 `token`, `name`, `source_url`, `source_platform`, `source_platform_label`, `offer_count`, `in_stock_count`, `product_count`, `first_seen_at`, `last_seen_at`, `last_success_at`, `product_slugs` 等字段。
- `ShopListResponse`：分页响应结构 `{ items: list[ShopCard], total: int }`。

### Catalog 服务升级 (`catalog.py`)
在 [catalog.py](file:///C:/Users/59908/ai_price_radar_v3/apps/api/app/services/catalog.py) 中新增 `list_public_shops()`：
- 严格遵循 `Shop.is_visible = True`、`Offer.active = True`、`Offer.approved = True` 且报价在有效时间窗口内的过滤规则，杜绝空店和已失效店铺。
- 支持 `source_platform`, `q`, `offset`, `limit`, `sort` 筛选参数。

### 接口路由 (`public.py`)
在 [public.py](file:///C:/Users/59908/ai_price_radar_v3/apps/api/app/routers/public.py) 中：
- 保留 `GET /api/v1/shops` 返回 `list[str]` token 列表，维持既有调用契约。
- 新增 `GET /api/v1/shops/cards` 返回分页 `ShopListResponse`，供店铺目录和来源页使用。
- 保留 `GET /api/v1/shops/tokens` 作为语义明确的轻量 token 列表接口。

---

## 3. 前端 SEO 专题层与信息架构建设

### 品牌关联 (`layout.tsx`)
修改根布局 [layout.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/layout.tsx)：
- Title template 更新为 `%s · AI Price Radar · PriceMemo`，在搜索引擎中建立域名品牌与站点的关联。

### 店铺详情页 SEO 强化 (`shops/[token]/page.tsx`)
完善 [shops/[token]/page.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/shops/%5Btoken%5D/page.tsx)：
- 补全 `description`, `canonical`, `robots`（有公开报价才 index，否则 noindex），`openGraph`。
- 在页面中新增“涉及标准产品”内链区块，打通 `Shop ↔ Product` 实体链接。

### 新增店铺目录页 (`shops/page.tsx`)
新增 [shops/page.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/shops/page.tsx)：
- 统一公开店铺索引，支持按平台筛选（16688, LDXP, 独角等）。
- 服务端组件（Server Component）直出 HTML，提供稳定的目录抓取入口。

### 新增来源专题页 (`sources/page.tsx` & `sources/[source]/page.tsx`)
- [sources/page.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/sources/page.tsx)：来源平台总览导航。
- [sources/[source]/page.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/sources/%5Bsource%5D/page.tsx)：来源详情页（如 `/sources/16688`），提供该来源专属统计、热门标准产品列表与关联店铺列表。
- 16688 专用 SEO 文案（H1、Title、Description）针对“16688 AI 商品与店铺报价”精准优化。

### 新增来源×产品交叉页 (`sources/[source]/products/[slug]/page.tsx`)
新增 [sources/[source]/products/[slug]/page.tsx](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/sources/%5Bsource%5D/products/%5Bslug%5D/page.tsx)：
- 覆盖如 `/sources/16688/products/chatgpt-access-service`（Codex 接码/验证服务报价）与 `/sources/16688/products/codex-access`（Codex 账号与访问）。
- 包含面包屑导航（Breadcrumb）、统计卡片、报价明细表以及双向返回链接。
- 报价数量充足时（>=2 条）自动启用 `index,follow`。

### 动态 Sitemap 扩充 (`sitemap.ts`)
更新 [sitemap.ts](file:///C:/Users/59908/ai_price_radar_v3/apps/web/app/sitemap.ts)：
- 纳入 `/shops`, `/sources` 静态入口。
- 动态纳入各有效来源平台页 `/sources/{platform}`。
- 动态纳入所有有真实报价的店铺 `/shops/{token}`。
- 动态纳入有报价沉淀的来源×产品交叉页 `/sources/{platform}/products/{slug}`。

---

## 4. 验证测试结果

| 测试套件 | 验证命令 | 结果 |
| :--- | :--- | :--- |
| **Crawler 发现测试** | `pytest tests/test_source_discovery.py` | ✅ **17 passed** |
| **API 单元测试** | `pytest apps/api/tests/` | ✅ **162 passed** (含新增 /shops 过滤与 tokens 测试) |
| **Pipeline 测试** | `pytest pipeline/tests/` | ✅ **194 passed** |
| **Next.js 生产构建** | `npm run build` | ✅ **64/64 static pages & dynamic routes generated** |
