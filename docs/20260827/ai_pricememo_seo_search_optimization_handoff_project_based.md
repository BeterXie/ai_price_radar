# AI Price Radar — SEO / 搜索引擎检索优化交接文档

- 项目：`BeterXie/ai_price_radar`
- 站点：`https://ai.pricememo.cn`
- 代码基线：`main`
- 基线提交：`6d591e8c2d6a78557ff85f5cd0be929c342fcb7a`
- 文档日期：2026-08-27
- 核心目标：让 Google / Bing / AI 搜索在查询 `16688 + ChatGPT / Codex / 接码 / Claude / Gemini / Grok / 店铺` 等组合词时，更容易理解并命中 AI Price Radar。

> 本文档基于当前 Next.js / FastAPI 代码结构编写。当前项目已经有较完善的产品 SEO 基础，优化重点不是“重做 SEO”，而是补足 **Source → Shop → Product** 这一层可索引信息架构。

---

# 1. 当前结论

`ai.pricememo.cn` 目前并不是“没有 SEO”。

项目已经具备：

- Next.js Metadata；
- 首页 canonical；
- 产品页 canonical；
- 查询参数页 `noindex,follow`；
- 动态 sitemap；
- robots.txt；
- 产品独特 SEO 文案；
- Product / Offer 结构化数据基础；
- OpenGraph；
- Twitter metadata；
- Guide 内容体系；
- 标准产品清晰 URL；
- 服务端渲染的数据页面。

当前搜索“16688 Codex 接码 店铺”不容易命中的核心原因是：

> **站点虽然有 16688 报价数据和店铺详情页，但搜索引擎缺少一个明确、稳定、可抓取的“16688 来源专题层”。**

当前信息架构更像：

```text
AI Price Radar
├─ products
├─ product detail
├─ guides
└─ shops/{token}
```

搜索引擎缺少：

```text
sources
└─ 16688
   ├─ shops
   ├─ ChatGPT
   ├─ Codex / 接码
   ├─ Claude
   ├─ Gemini
   └─ Grok
```

---

# 2. 当前 SEO 实现盘点

## 2.1 Root Metadata

文件：

```text
apps/web/app/layout.tsx
```

当前：

```ts
export const metadata: Metadata = {
  metadataBase: new URL("https://ai.pricememo.cn"),
  title: { default: "AI Price Radar", template: "%s · AI Price Radar" },
  description: "聚合公开 AI 订阅商品报价，比较价格、库存、来源和更新时间。",
  openGraph: { siteName: "AI Price Radar", locale: "zh_CN", type: "website" },
};
```

这部分基础正确。

问题不是技术错误，而是品牌关联较弱：

```text
AI Price Radar
```

和域名品牌：

```text
PriceMemo
```

没有明显建立文本关系。

---

# 3. 首页当前 Metadata

文件：

```text
apps/web/app/page.tsx
```

当前 title：

```text
AI 订阅比价｜查价格、库存和交付方式
```

description：

```text
汇总 ChatGPT、Claude、Gemini、Grok 等 AI 产品的公开报价，比较价格、库存、交付方式和更新时间。
```

优点：

- 有 ChatGPT；
- 有 Claude；
- 有 Gemini；
- 有 Grok；
- 搜索意图明确；
- canonical 正确。

缺口：

```text
Codex
16688
PriceMemo
店铺 / 来源
```

没有出现在首页核心 metadata。

但不建议把所有关键词硬塞首页。

更好的方式是：

> 首页继续负责“AI 比价”大词，`16688 / Codex 接码 / 店铺来源` 交给专门 landing page。

---

# 4. 产品页 SEO 已经比较成熟

文件：

```text
apps/web/app/products/[slug]/page.tsx
```

当前已经：

```text
generateMetadata()
canonical
robots
OpenGraph
Twitter
```

无报价产品：

```text
noindex,follow
```

带查询参数：

```text
indexable = false
```

canonical：

```text
/products/{slug}
```

这个设计方向正确。

---

# 5. 产品 SEO 内容已经覆盖 Codex 接码

文件：

```text
apps/web/lib/product-seo.ts
```

已有：

```text
chatgpt-access-service
```

metaDescription：

> 查看 ChatGPT 与 Codex 接码、验证、提链、邮箱等周边服务公开报价，不与会员价格混算。

同时已有：

```text
codex-access
```

因此站点实际上已经有：

```text
Codex
Codex 接码
验证
```

相关 SEO 语义。

问题是：

> 它们目前没有与“16688 来源”组合成独立可索引页面。

---

# 6. Sitemap 当前最大缺口

文件：

```text
apps/web/app/sitemap.ts
```

当前 Sitemap 包含：

```text
/
 /products
 /tools/json-to-cockpit
 /shops/submit
 /watchlist
 /methodology
 /corrections
 /developers
 /about
 /privacy
 /terms
 /security

/guides...
/products/{slug}
```

但当前 **不包含：**

```text
/shops/{token}
```

也没有：

```text
/sources
/sources/16688
/sources/16688/products/{slug}
```

这是当前最直接的 SEO 缺口之一。

---

# 7. 店铺页当前 SEO 很弱

文件：

```text
apps/web/app/shops/[token]/page.tsx
```

当前：

```ts
export async function generateMetadata(...) {
  const shop = await getShop(token);
  return { title: shop ? `${shop.name}报价` : "店铺不存在" };
}
```

只有：

```text
title
```

缺少：

```text
description
canonical
robots
openGraph
twitter
source platform keyword
```

例如 16688 店铺页面现在没有明确告诉搜索引擎：

```text
这个页面是 16688 来源
这个店铺有哪些 AI 商品
这个页面应该 canonical 到哪里
当前是否值得 index
```

---

# 8. 店铺页虽然存在，但没有“目录入口”

当前有：

```text
/shops/[token]
/shops/submit
```

但没有明确的：

```text
/shops
```

公开目录页。

这造成：

```text
产品页
  ↓
某个报价
  ↓
店铺详情
```

虽然用户可以点击进入，但搜索引擎没有一个稳定的店铺集合页帮助理解站点实体关系。

---

# 9. 当前公开 API 已经支持 source_platform 过滤

文件：

```text
apps/api/app/routers/public.py
```

`GET /api/v1/products` 已支持：

```text
source_platform
```

`GET /api/v1/catalog/groups` 也支持：

```text
source_platform
```

`GET /api/v1/products/{slug}` 同样支持：

```text
source_platform
```

因此数据层已经具备：

```text
只看 16688
```

的能力。

问题只是：

> 这个能力现在主要通过 query param 使用，没有成为正式 SEO URL。

---

# 10. 当前 Query Param 页面被正确 noindex

例如：

```text
/products?source_platform=16688
```

当前 `/products` metadata 逻辑：

```text
Object.keys(params).length
    ? noindex
    : index
```

这是合理的。

不要为了 SEO 直接把所有：

```text
?source_platform=...
?in_stock=...
?min_price=...
```

开放 index。

否则会制造大量：

```text
filter combination duplicate pages
```

正确做法是：

> 为需要 SEO 的少数重要维度创建独立 canonical route。

---

# 11. SEO 目标信息架构

推荐新增：

```text
/sources
/sources/16688
/sources/16688/products/chatgpt-plus
/sources/16688/products/chatgpt-access-service
/sources/16688/products/codex-access
/sources/16688/products/claude-pro
/sources/16688/products/gemini-advanced
/sources/16688/products/grok-super
```

继续保留：

```text
/shops/{token}
```

建议再补：

```text
/shops
```

---

# 12. 为什么建议使用标准 product slug

不要新建一套 SEO-only taxonomy：

```text
/sources/16688/codex-sms
/sources/16688/openai-plus
```

如果内部标准产品已经有：

```text
chatgpt-access-service
codex-access
chatgpt-plus
```

更好的 URL 是：

```text
/sources/16688/products/chatgpt-access-service
/sources/16688/products/codex-access
/sources/16688/products/chatgpt-plus
```

优点：

- 与数据库 Product.slug 一致；
- 与 API 一致；
- 不产生第二套分类；
- 后续 sitemap 自动生成容易；
- canonical 清晰。

页面标题仍可以用更自然的搜索词：

```text
16688 Codex 接码与验证服务报价
```

而 URL 不需要写中文关键词。

---

# 13. P0：新增 Source Landing Page

建议新建：

```text
apps/web/app/sources/page.tsx
apps/web/app/sources/[source]/page.tsx
```

第一期至少支持：

```text
16688
ldxp
dujiao_next
merchant_json
woocommerce
schema_org
```

但 SEO 内容优先写 16688。

---

# 14. `/sources/16688` 页面应展示什么

服务端输出真实数据。

建议：

```text
H1:
16688 AI 商品与店铺报价

Intro:
AI Price Radar 汇总来自 16688 公开店铺的
ChatGPT、Codex、Claude、Gemini、Grok 等公开报价。

统计：
当前有效报价
当前店铺数
有货报价数
最近更新时间

热门标准产品：
ChatGPT Plus
ChatGPT Pro
Codex 账号与访问
ChatGPT / Codex 接码与验证服务
Claude Pro
Gemini Advanced
SuperGrok

当前店铺：
店名
店铺 token
报价数
最后观测时间
```

要求：

> 上述文字必须由 Next.js Server Component 直接输出 HTML，不能只在客户端交互后才出现。

当前项目本身就是 Server Component 架构，不需要为了这个目标再改一次 SSR 框架。

---

# 15. P0：新增 Public Shops List API

当前只有：

```text
GET /api/v1/shops/{token}
```

没有：

```text
GET /api/v1/shops
```

建议新增：

```text
GET /api/v1/shops
```

参数：

```text
q
source_platform
offset
limit
sort
```

建议默认只返回：

```text
Shop.is_visible = true
当前 snapshot 有公开 Offer
Offer.active = true
Offer.approved = true
Offer.product_id != null
报价未过期
```

避免 sitemap 和店铺目录出现：

```text
空店
失效店
无公开商品店
```

---

# 16. 建议新增 ShopCard schema

API：

```text
apps/api/app/schemas.py
```

前端类型：

```text
apps/web/lib/types.ts
```

建议字段：

```text
token
name
source_url
source_platform
source_platform_label
offer_count
in_stock_count
product_count
first_seen_at
last_seen_at
last_success_at
```

可以再带：

```text
product_slugs
```

但不需要返回全部 offers。

---

# 17. 建议新增 catalog service

文件：

```text
apps/api/app/services/catalog.py
```

新增：

```python
list_public_shops(...)
```

不要在 Router 内写复杂 SQL。

复用当前：

```text
_base_public_offer_query()
```

或者抽一个公共 shop/offer query helper。

目标：

```text
Shop
  + public offer count
  + in stock count
  + distinct product count
  + last observed
```

---

# 18. P0：完善 Shop Page Metadata

文件：

```text
apps/web/app/shops/[token]/page.tsx
```

建议：

```ts
export async function generateMetadata({ params }): Promise<Metadata> {
  const { token } = await params;
  const shop = await getShop(token);

  if (!shop) {
    return {
      title: "店铺不存在",
      robots: { index: false, follow: true },
    };
  }

  const canonical =
    `https://ai.pricememo.cn/shops/${encodeURIComponent(shop.token)}`;

  const description =
    `查看 ${shop.name} 在 ${shop.source_platform_label} 的 AI 商品公开报价、库存、交付方式、更新时间和原始来源。`;

  return {
    title: `${shop.name}｜${shop.source_platform_label} AI 商品报价`,
    description,
    alternates: { canonical },
    robots: {
      index: shop.offer_count > 0,
      follow: true,
    },
    openGraph: {
      title: `${shop.name}｜${shop.source_platform_label} AI 商品报价`,
      description,
      url: canonical,
      type: "website",
    },
  };
}
```

对于 16688 店铺，搜索引擎会直接看到：

```text
店铺名
16688
AI 商品报价
```

---

# 19. 店铺页正文也应增加可索引语义

当前页面已有：

```text
公开来源
来源编号
采集方式
收录时间
当前报价
```

建议补：

```text
该店铺当前涉及哪些标准产品
```

例如：

```text
ChatGPT Plus
Codex 账号与访问
ChatGPT / Codex 接码与验证
Claude Pro
```

不要靠搜索框猜。

从真实 offers 中聚合 Product.slug / display_name。

---

# 20. P0：把公开店铺加入 Sitemap

当前：

```text
apps/web/app/sitemap.ts
```

建议新增：

```text
getShops()
```

然后：

```text
/shops/{token}
```

进入 sitemap。

进入条件：

```text
offer_count > 0
```

`lastModified`：

优先：

```text
last_seen_at
```

fallback：

```text
last_success_at
```

再 fallback：

```text
first_seen_at
```

---

# 21. Sitemap 还要加入 Source Pages

固定：

```text
/sources
```

动态：

```text
/sources/{source_platform}
```

只为当前实际有公开报价的平台生成。

来源数据可以来自：

```text
GET /api/v1/meta
```

因为当前 `Meta` 已经返回：

```text
source_platforms
```

---

# 22. Source × Product Sitemap

推荐只生成有实际报价的组合。

例如：

```text
/sources/16688/products/chatgpt-plus
/sources/16688/products/chatgpt-access-service
```

不要生成：

```text
16688 × 所有标准产品
```

必须满足：

```text
offer_count > 0
```

否则会产生大量薄内容页面。

---

# 23. P1：Source × Product 页面

建议路由：

```text
apps/web/app/sources/[source]/products/[slug]/page.tsx
```

API 查询直接复用：

```text
GET /api/v1/products/{slug}?source_platform=16688
```

但 canonical 指向：

```text
/sources/16688/products/{slug}
```

而不是通用：

```text
/products/{slug}
```

前提：

> 这个 source-specific 页面确实有独立数据和独立内容。

---

# 24. Source × Product 页面内容模板

例如：

```text
/sources/16688/products/chatgpt-access-service
```

Title：

```text
16688 Codex 接码与验证服务报价
```

Description：

```text
查看 16688 公开店铺中的 ChatGPT / Codex 接码、验证码、验证与开通辅助服务报价、库存、店铺和最近更新时间。
```

H1：

```text
16688 Codex 接码与验证服务
```

正文：

```text
当前报价数量
当前店铺数量
当前有货数量
最近更新时间
价格范围
涉及店铺
原始商品标题
```

不要伪造：

```text
“最佳”
“最安全”
“最可信”
```

除非项目有明确可验证依据。

---

# 25. Codex 需要两个落地意图

当前数据模型中有：

```text
codex-access
chatgpt-access-service
```

因此 SEO 应明确拆两个搜索意图：

## Codex 账号 / 访问

```text
/sources/16688/products/codex-access
```

搜索意图：

```text
16688 Codex
Codex账号
Codex访问
Codex购买
```

## Codex 接码 / 验证

```text
/sources/16688/products/chatgpt-access-service
```

搜索意图：

```text
16688 Codex接码
Codex验证码
Codex短信验证
OpenAI接码
```

这样不需要改数据库分类，也能覆盖两个 SERP intent。

---

# 26. 首页不要堆 16688

首页继续保持：

```text
AI 商品比价
```

可以适度修改品牌关联。

例如：

```text
AI Price Radar｜ChatGPT、Codex、Claude、Gemini、Grok 比价 - PriceMemo
```

但建议先观察 title 长度。

更稳妥：

Root template：

```text
%s · AI Price Radar · PriceMemo
```

或者首页 title：

```text
AI Price Radar｜AI 订阅与账号公开报价 - PriceMemo
```

不要在首页 title 强塞：

```text
16688
LDXP
Dujiao
WooCommerce
...
```

来源平台词应该由 `/sources/*` 承担。

---

# 27. Root Brand 建议

文件：

```text
apps/web/app/layout.tsx
```

可以将：

```ts
title: {
  default: "AI Price Radar",
  template: "%s · AI Price Radar"
}
```

调整为：

```ts
title: {
  default: "AI Price Radar · PriceMemo",
  template: "%s · AI Price Radar · PriceMemo"
}
```

这样搜索引擎能逐渐建立：

```text
AI Price Radar
↔
PriceMemo
↔
ai.pricememo.cn
```

---

# 28. Structured Data 建议

当前产品页已经有产品结构化数据基础。

新增页面建议：

## `/sources/16688`

使用：

```text
CollectionPage
ItemList
```

## `/shops/{token}`

使用：

```text
WebPage
ItemList
```

如果页面本质上只是线上来源实体，不要为了 rich result 强行标：

```text
LocalBusiness
```

更不要虚构：

```text
aggregateRating
reviewCount
```

---

# 29. Breadcrumb

建议为：

```text
首页
→ 来源平台
→ 16688
→ Codex 接码
```

店铺：

```text
首页
→ 店铺
→ 16688
→ 店铺名
```

页面可使用：

```text
BreadcrumbList
```

结构化数据。

---

# 30. Internal Linking

产品报价列表里当前已经有：

```text
shop_token
shop_name
source_platform
```

应确保：

```text
shop_name
```

始终是指向：

```text
/shops/{shop_token}
```

的内部链接。

同时店铺页应反链：

```text
/products/{slug}
```

Source page 再链接：

```text
/shops/{token}
/sources/16688/products/{slug}
```

最终形成：

```text
Source
↔ Shop
↔ Product
```

而不是孤立页面。

---

# 31. 不要把筛选 URL 全部 index

继续保持：

```text
/products?...
```

noindex。

不要 index：

```text
?in_stock=true
?sort=price
?min_price=
?max_price=
?warranty=
?updated_within_hours=
```

这些没有独立稳定搜索意图。

只有下列维度值得独立 route：

```text
source
standard product
source × standard product
shop
```

---

# 32. Server Rendering 当前已经满足

文件：

```text
apps/web/lib/api.ts
```

当前：

```ts
fetch(..., { cache: "no-store" })
```

页面使用 Next.js Server Components。

所以：

```text
无需“把页面改成 SSR”
```

真正需要保证：

```text
搜索引擎请求页面时，
title / H1 / intro / 店铺列表 / 产品列表
已经存在于返回 HTML 中。
```

Source page 不要写成：

```text
"use client"
useEffect(fetch)
```

后才填正文。

---

# 33. `force-dynamic` 不是本轮 SEO 阻塞点

当前产品页、店铺页、sitemap 都使用：

```ts
export const dynamic = "force-dynamic";
```

这不会导致页面天然不可索引。

第一阶段不要为了 SEO 大规模改：

```text
SSR → ISR
dynamic → static
```

先补信息架构。

后续若有性能压力，再根据：

```text
crawl frequency
API load
snapshot frequency
```

考虑：

```text
revalidate
ISR
cache tags
```

---

# 34. P0 文件改动清单

## API

```text
apps/api/app/schemas.py
```

新增：

```text
ShopCard
ShopPage
```

```text
apps/api/app/services/catalog.py
```

新增：

```text
list_public_shops()
```

```text
apps/api/app/routers/public.py
```

新增：

```text
GET /api/v1/shops
```

---

## Web types / API

```text
apps/web/lib/types.ts
```

新增：

```text
ShopCard
ShopPage
```

```text
apps/web/lib/api.ts
```

新增：

```ts
getShops(query)
```

---

## Web routes

新增：

```text
apps/web/app/shops/page.tsx

apps/web/app/sources/page.tsx
apps/web/app/sources/[source]/page.tsx
apps/web/app/sources/[source]/products/[slug]/page.tsx
```

---

## Existing routes

修改：

```text
apps/web/app/shops/[token]/page.tsx
apps/web/app/sitemap.ts
apps/web/app/layout.tsx
```

---

# 35. P0 测试清单

## API

建议新增/扩展：

```text
apps/api/tests/
```

测试：

- [ ] `/api/v1/shops` 只返回 visible shop。
- [ ] 必须有当前公开 Offer。
- [ ] `source_platform=16688` 过滤正确。
- [ ] offset/limit 正确。
- [ ] 空店不出现。
- [ ] 过期报价店铺不出现。
- [ ] source platform label 正确。

---

## Web

建议增加：

```text
apps/web/tests/
```

测试：

- [ ] `/sources/16688` title 包含 `16688`。
- [ ] `/sources/16688` 有 canonical。
- [ ] `/shops/16688-xxx` metadata 包含来源平台。
- [ ] 空报价 shop 为 noindex。
- [ ] 有报价 shop 为 index。
- [ ] sitemap 包含有报价店铺。
- [ ] sitemap 不包含空店。
- [ ] sitemap 包含 `/sources/16688`。
- [ ] source × product 无报价时不进 sitemap。

---

# 36. 推荐 Metadata 模板

## Source

```text
Title:
16688 AI 商品与店铺报价｜ChatGPT、Codex、Claude、Gemini、Grok

Description:
查看来自 16688 公开店铺的 ChatGPT、Codex、Claude、Gemini、Grok 商品报价、库存、店铺和最近更新时间。
```

---

## Shop

```text
Title:
{店铺名}｜16688 AI 商品报价

Description:
查看 {店铺名} 在 16688 的 AI 商品公开报价、库存、交付方式、更新时间和原始来源。
```

---

## 16688 + Codex Access

```text
Title:
16688 Codex 账号与访问报价

Description:
比较 16688 公开店铺中的 Codex 账号、访问服务、库存、交付方式、店铺和更新时间。
```

---

## 16688 + Codex 接码

```text
Title:
16688 Codex 接码与验证码服务报价

Description:
查看 16688 公开店铺中的 Codex 接码、验证码、短信验证和辅助开通服务报价、库存与来源。
```

---

# 37. Sitemap 生成建议

当前 `sitemap.ts` 已经：

```text
getProducts()
```

建议再：

```text
getMeta()
getShops()
```

逻辑：

```text
static pages
+
guide pages
+
visible product pages
+
active source pages
+
public shop pages
+
source × product pages with actual offers
```

若 API 获取失败：

继续沿用现在设计：

```text
返回可用的静态 sitemap
```

不要因为 Shops API 临时失败让整个 sitemap 500。

---

# 38. SEO 页面数量控制

不要一次生成：

```text
10000 个 thin page
```

建议第一阶段：

```text
所有有公开报价的 shop
+
所有有报价 source
+
source × product 且 offer_count > 0
```

如果某 source-product 只有 1 条短期报价，也可以先：

```text
noindex,follow
```

建议设置门槛：

```text
offer_count >= 2
或
shop_count >= 2
```

再 index。

具体门槛上线后根据 Search Console 调整。

---

# 39. 站内搜索与 SEO 不要混为一谈

项目已有：

```text
q
brand
product
source_platform
delivery_type
...
```

用于用户检索。

SEO landing page 是：

```text
稳定 URL
稳定主题
稳定 canonical
服务端正文
真实聚合数据
```

不要让：

```text
用户每个搜索词
```

都自动创建一个 indexable 页面。

---

# 40. Search Console / Bing Webmaster 验收

上线后必须检查：

```text
/sources/16688
/shops/{一个16688真实token}
/sources/16688/products/chatgpt-access-service
/sources/16688/products/codex-access
```

确认：

```text
HTTP 200
canonical self-reference
robots index/follow
页面源码含正文
sitemap 已包含
无重复 canonical
无 soft 404
```

---

# 41. 搜索词验收集合

至少持续观察：

```text
AI Price Radar
PriceMemo AI
ChatGPT 比价
Codex 比价
Codex 接码
Codex 验证码
16688 AI
16688 ChatGPT
16688 Codex
16688 Codex 接码
16688 Claude
16688 Gemini
16688 Grok
16688 店铺
```

---

# 42. 成功指标

## 技术指标

```text
Indexed source pages
Indexed shop pages
Indexed source-product pages
Sitemap discovered URLs
Canonical errors
Crawl errors
```

## 搜索表现

```text
Impressions
Clicks
CTR
Average position
Query coverage
```

重点对比：

```text
16688
Codex
接码
店铺
```

相关长尾词。

---

# 43. 本轮优先级

```text
P0
├─ GET /api/v1/shops
├─ /shops 目录
├─ /sources
├─ /sources/16688
├─ Shop metadata
└─ Shop + Source sitemap

P1
├─ /sources/16688/products/{slug}
├─ Breadcrumb
├─ CollectionPage / ItemList JSON-LD
└─ Source ↔ Shop ↔ Product 内链

P2
├─ Search Console 数据驱动标题调整
├─ 根据 crawl/load 做 ISR
├─ 分析 thin source-product page
└─ 品牌词 AI Price Radar ↔ PriceMemo 强化
```

---

# 44. 不建议做的 SEO 改动

不要：

```text
❌ meta keywords 堆砌
❌ 首页塞几十个来源名
❌ index 所有筛选 query
❌ 自动生成任意用户搜索结果页
❌ 虚构商家评分
❌ 虚构评论数量
❌ 给线上店铺强套 LocalBusiness
❌ 复制第三方聚合网站商品描述
❌ 为 SEO 建第二套 Product 分类
❌ 为 SEO 把现有 Server Component 全改 Client
```

---

# 45. 版本与文档注意事项

仓库当前存在：

```text
RELEASE_NOTES_v3.7.14.md
```

且 16688 端到端支持已经进入代码。

但部分旧文档仍保留：

```text
v3.2.x
```

版本描述。

因此接手开发时：

> 以 Git `main` HEAD、Tag/Release、CI 和 `docs/QUICK_DEPLOY.md` 为部署依据，不要单靠旧 `docs/HANDOVER.md` 或 README 中的历史版本号判断生产版本。

---

# 46. 部署要求

仓库：

```text
AGENTS.md
```

已经明确要求生产部署：

1. 先读 `docs/QUICK_DEPLOY.md`；
2. 不从未打 Tag 的 commit 部署；
3. 不从 dirty worktree 部署；
4. CI 失败不能部署；
5. 生产切换前若关键步骤失败必须停止。

本 SEO 改造涉及：

```text
API
Web
Sitemap
```

上线时必须遵循现有 release runbook。

---

# 47. 接收方第一步

建议按以下顺序阅读：

```text
apps/web/app/layout.tsx
apps/web/app/page.tsx
apps/web/app/products/page.tsx
apps/web/app/products/[slug]/page.tsx
apps/web/app/shops/[token]/page.tsx
apps/web/app/sitemap.ts
apps/web/app/robots.ts

apps/web/lib/api.ts
apps/web/lib/types.ts
apps/web/lib/product-seo.ts

apps/api/app/routers/public.py
apps/api/app/services/catalog.py
apps/api/app/services/source_platform.py
apps/api/app/models.py
apps/api/app/schemas.py
```

然后先实现：

```text
GET /api/v1/shops?source_platform=16688
```

验证数据正确后，再做：

```text
/sources/16688
```

最后才扩 sitemap。

---

# 48. 一句话交接

> AI Price Radar 当前产品 SEO 已经具备 canonical、noindex、动态 sitemap 和独特商品文案；真正阻碍“16688 Codex 接码店铺”这类搜索命中的，是缺少 Source → Shop → Product 的可索引信息架构。第一优先级不是重写 SSR，而是新增公开 Shops API、`/sources/16688`、完善 `/shops/{token}` metadata，并把真实有报价的店铺与来源页加入 Sitemap。
