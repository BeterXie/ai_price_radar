# 16688 Discovery 召回 + SEO 信息架构优化

基于 `docs/20260827/` 下两份交接文档，对项目进行系统优化。涵盖两大方向：
1. **16688 店铺发现召回率提升** — 扩展 Bing 搜索词覆盖
2. **SEO 信息架构补足** — 新增 Source/Shop 可索引页面层、完善 metadata 与 sitemap

> [!IMPORTANT]
> 本次改动严格遵循交接文档原则：复用现有 Unified Source Discovery / Detector / Connector / Atomic Publish 链路，不新增第二套并行发布体系。SEO 页面使用 Server Component 直出，不改现有 SSR 架构。

---

## Proposed Changes

### Component 1: 16688 Discovery 关键词扩展（P0）

#### [MODIFY] [keywords.py](file:///c:/Users/59908/ai_price_radar_v3/crawler/ldxp/ldxp_crawler/source_discovery/keywords.py)

重写 `bing_16688_queries()` 函数：
- 移除 `del keywords`，不再丢弃传入参数（保持接口兼容，但暂不使用外部 keywords 做笛卡尔积）
- 扩展高价值搜索词列表：
  - 第一优先级品牌词：`ChatGPT`, `Codex`, `OpenAI`, `Claude`, `Gemini`, `Grok`
  - 第二优先级产品词：`ChatGPT Plus`, `ChatGPT Pro`, `SuperGrok`, `Claude Pro`, `Gemini Advanced`, `OpenAI API`
  - 第三优先级服务词：`Codex 接码`, `接码`, `验证码`, `成品号`
- 所有查询仍限定 `site:16688.com.cn/shop` 域名
- 保持固定列表，不做无限组合，控制 Bing RSS 查询预算

---

#### [MODIFY] [test_source_discovery.py](file:///c:/Users/59908/ai_price_radar_v3/crawler/ldxp/tests/test_source_discovery.py)

扩展 `test_keywords_are_deduplicated_and_include_brand_and_chinese_terms` 测试：
- 断言 `bing_16688_queries()` 包含 `Codex`
- 断言包含接码/验证码类查询
- 断言包含 ChatGPT / Claude / Gemini / Grok
- 断言所有查询均限制 `site:16688.com.cn/shop`
- 断言无重复查询
- 新增独立测试函数 `test_bing_16688_queries_coverage`

---

### Component 2: Public Shops API 升级（P0）

#### [MODIFY] [schemas.py](file:///c:/Users/59908/ai_price_radar_v3/apps/api/app/schemas.py)

新增两个 Pydantic schema：
- `ShopCard` — 店铺摘要卡片：`token`, `name`, `source_url`, `source_platform`, `source_platform_label`, `offer_count`, `in_stock_count`, `product_count`, `first_seen_at`, `last_seen_at`, `last_success_at`, `product_slugs`
- `ShopListResponse` — 分页响应：`items: list[ShopCard]`, `total: int`

---

#### [MODIFY] [catalog.py](file:///c:/Users/59908/ai_price_radar_v3/apps/api/app/services/catalog.py)

新增 `list_public_shops()` 服务函数：
- 复用 `_base_public_offer_query()` 的公开 offer 条件
- 按 Shop 聚合：offer_count, in_stock_count, distinct product count
- 支持 `source_platform`, `q` (名称搜索), `offset`, `limit`, `sort` 参数
- 只返回 `Shop.is_visible = True` 且有公开 Offer 的店铺

---

#### [MODIFY] [public.py](file:///c:/Users/59908/ai_price_radar_v3/apps/api/app/routers/public.py)

升级 `GET /api/v1/shops` 端点：
- 当前返回 `list[str]`（token 列表）
- 新增查询参数：`q`, `source_platform`, `offset`, `limit`, `sort`
- 默认行为：当无筛选参数时，保持返回 `list[str]` 以兼容现有 sitemap 调用
- 当带有 `detail=true` 或其他筛选参数时，返回 `ShopListResponse`

> [!NOTE]
> 为保持向后兼容，采用双模式端点设计。现有 `getShopTokens()` 前端调用无需改动。新增一个独立端点 `GET /api/v1/shops/cards` 返回 `ShopListResponse`，避免破坏现有接口。

---

### Component 3: 前端类型与 API 层（P0）

#### [MODIFY] [types.ts](file:///c:/Users/59908/ai_price_radar_v3/apps/web/lib/types.ts)

新增类型定义：
```ts
export type ShopCard = {
  token: string;
  name: string;
  source_url: string;
  source_platform: string;
  source_platform_label: string;
  offer_count: number;
  in_stock_count: number;
  product_count: number;
  first_seen_at: string;
  last_seen_at: string | null;
  last_success_at: string | null;
  product_slugs: string[];
};

export type ShopListResponse = {
  items: ShopCard[];
  total: number;
};
```

---

#### [MODIFY] [api.ts](file:///c:/Users/59908/ai_price_radar_v3/apps/web/lib/api.ts)

新增 `getShopCards()` 函数：
```ts
export async function getShopCards(query = ""): Promise<ShopListResponse> { ... }
```

---

### Component 4: Root Brand 与 Shop Page SEO（P0）

#### [MODIFY] [layout.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/layout.tsx)

更新 title template 以关联品牌：
```ts
title: {
  default: "AI Price Radar · PriceMemo",
  template: "%s · AI Price Radar · PriceMemo"
}
```

---

#### [MODIFY] [shops/[token]/page.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/shops/%5Btoken%5D/page.tsx)

完善 `generateMetadata()`：
- 添加 `description`：`查看 ${shop.name} 在 ${shop.source_platform_label} 的 AI 商品公开报价、库存、交付方式、更新时间和原始来源。`
- 添加 `canonical`：`/shops/${token}`
- 添加 `robots`：有报价时 `index,follow`，无报价时 `noindex,follow`
- 添加 `openGraph`：title, description, url, type
- 店铺不存在时设置 `noindex`

在页面正文中新增"涉及标准产品"区块，从 offers 中聚合并展示 product slugs/names。

---

### Component 5: Shops 目录页（P0）

#### [NEW] [shops/page.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/shops/page.tsx)

公开店铺目录页：
- Server Component，`force-dynamic`
- 调用 `getShopCards()` 获取有公开报价的店铺列表
- 支持按 `source_platform` 筛选
- 展示店铺名、来源平台、报价数、有货数、最后观测时间
- 每个店铺名链接到 `/shops/{token}`
- Metadata：`title: "AI 来源店铺目录"`, `description`, `canonical: /shops`

---

### Component 6: Sources 页面体系（P0）

#### [NEW] [sources/page.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/sources/page.tsx)

来源平台总览页：
- 从 `getMeta()` 获取 `source_platforms` 列表
- 为每个平台展示名称和链接到 `/sources/{platform_id}`
- Metadata：`title: "来源平台"`

---

#### [NEW] [sources/[source]/page.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/sources/%5Bsource%5D/page.tsx)

来源平台详情页（如 `/sources/16688`）：
- Server Component，`force-dynamic`
- 调用 `getShopCards("source_platform=16688")` 获取该平台店铺
- 调用 `getProducts("source_platform=16688")` 获取该平台产品
- 展示：H1 标题、介绍文案、统计数据（报价数/店铺数/有货数）、热门产品列表、店铺列表
- 16688 专用 SEO metadata：
  - Title: `16688 AI 商品与店铺报价｜ChatGPT、Codex、Claude、Gemini、Grok`
  - Description: `查看来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 商品报价、库存、店铺和最近更新时间。`
- canonical: `/sources/16688`
- 产品链接到 `/products/{slug}?source_platform=16688`（后续 P1 改为 `/sources/16688/products/{slug}`）
- 店铺链接到 `/shops/{token}`

---

### Component 7: Sitemap 扩展（P0）

#### [MODIFY] [sitemap.ts](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/sitemap.ts)

新增 sitemap 条目：
1. 静态页：`/shops`, `/sources`
2. 动态来源页：从 `getMeta()` 获取 `source_platforms`，生成 `/sources/{platform_id}`
3. 店铺页已经存在（`shopTokens.map`），无需改动
4. 若 API 调用失败，fallback 仍然只返回静态页

---

### Component 8: Source × Product 页面（P1）

#### [NEW] [sources/[source]/products/[slug]/page.tsx](file:///c:/Users/59908/ai_price_radar_v3/apps/web/app/sources/%5Bsource%5D/products/%5Bslug%5D/page.tsx)

来源平台 × 标准产品交叉页：
- 复用 `getProduct(slug, "source_platform=16688")`
- canonical: `/sources/16688/products/{slug}`
- 仅在有实际报价时 index
- SEO title 使用产品自然语言名（如 `16688 Codex 接码与验证码服务报价`）

---

## Open Questions

> [!IMPORTANT]
> **API 兼容性策略**：当前 `GET /api/v1/shops` 返回 `list[str]`，前端 `getShopTokens()` 和 sitemap 都依赖此行为。建议新增独立端点 `GET /api/v1/shops/cards` 返回 `ShopListResponse`，而非修改现有端点。是否同意此方案？

> [!NOTE]
> **P1 / P2 阶段**：Breadcrumb JSON-LD、CollectionPage/ItemList 结构化数据、内链强化等 P1 任务是否在本次一并实现，还是先完成 P0 后再做？

---

## Verification Plan

### Automated Tests

```bash
# 1. Crawler keywords 测试
cd crawler/ldxp && python -m pytest tests/test_source_discovery.py -v -k "16688"

# 2. API 测试
cd apps/api && python -m pytest tests/ -v -k "shop"

# 3. Next.js 构建验证
cd apps/web && npx next build
```

### Manual Verification

- 访问 `/shops` 确认店铺目录页正常渲染
- 访问 `/sources` 确认来源平台列表正常
- 访问 `/sources/16688` 确认 16688 专题页内容正确、metadata 正确
- 访问 `/shops/{token}` 确认 metadata 包含 description/canonical/robots/openGraph
- 检查 `/sitemap.xml` 包含 `/shops`, `/sources/16688`, 各店铺 URL
- 验证 `bing_16688_queries()` 包含 Codex/接码/验证码等关键词
- 查看页面源码确认 SSR 输出含正文内容
