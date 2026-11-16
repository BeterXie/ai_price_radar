# v3.9.76 — Direct merchant ordering in the market table

The primary site's product rows now use the same market table as aiprice.si: product/category, merchant, price, stock, recent product activity and source. Each row exposes an ordering action. When multiple same-product shops exist, “去原站下单” opens the same shop-selection dialog as “同款 N 家”; only the selected merchant link navigates and records an outbound click. A single-shop quote links directly to its merchant. The primary site retains its readable cream theme and uses the shared mobile layout.

All five sites and their quote dialogs label outbound purchase links “去原站下单”. Market tables use a filled order button, an outlined same-product comparison button and a separate “商品详情” action. Comparison opens merchant quotes first; details opens the original description first. Prices, inventory and destinations continue to belong to the same displayed merchant; missing links and unavailable stock stay explicit. Pagination, filters, snapshot fallback, click tracking and the compact JEV LLMPort product are retained.

Primary catalog banners move into the table. A disclosed sponsor row follows every five products, including subsequently loaded products, using ordinary row dimensions. Brand-specific sponsorship takes priority over the existing catalog or product placement; disabled and absent ads remain hidden. Existing advertising destinations and click tracking are retained, with no invented stock or price for sponsors.

No database migration, crawler or pipeline change. Follow `QUICK_DEPLOY.md` and `MULTI_BRAND_DEPLOY.md`: deploy the clean published tag after CI, preserve the database/source/image rollback point, run staging preflight, rebuild API and importer, and build and switch all five frontends. No full refresh is required for this release.

Validate desktop and mobile rows, the same-product dialog, missing-link and stock states, pagination, the JEV card, and all five sites' version and health checks.
