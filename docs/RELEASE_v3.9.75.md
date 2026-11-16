# v3.9.75 — Clear merchant purchasing and compact JEV product

The primary catalog previously showed only a small expansion arrow, then placed shop links below long product details. Product rows now say “查看店铺报价”; opening a row shows merchant prices and prominent “去店铺下单” links first. Mobile titles use two lines while collapsed and expand in full. Delivery, period and warranty appear with each shop quote. Out-of-stock offers say “去店铺查看”; missing links do not offer checkout. Purchasing remains on the merchant website, with existing snapshot recovery and click tracking.

The primary `/brands/jev` page now shows one compact LLMPort product using its approved, enabled relay identity and registration URL. It replaces the sponsor slot and empty quote controls. The owner-provided copy describes JEV at half the official price, millisecond latency and USD 1 of signup trial credit. OpenAI relay metrics are not presented as JEV measurements. Other brand sites retain their existing catalog composition.

No database migration, crawler or pipeline change. Follow `QUICK_DEPLOY.md` and `MULTI_BRAND_DEPLOY.md`: deploy the clean published tag after CI, preserve the database/source/image rollback point, run staging preflight, rebuild API and importer, and build and switch all five frontends. No full refresh is required for this release.

Validate the mobile and desktop purchase flow, missing-link and stock states, JEV relay availability and destination, the ordinary brand catalog, and all five sites' version and health checks.
