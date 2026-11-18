# v3.9.87

QQ and Telegram price reports now display snapshot publication time in Beijing time (UTC+8). QQ price-drop rows include the original merchant product URL.

The scheduled inventory and full-catalog publisher checks every successfully exported current snapshot for available OpenAI Team 5x / 10x and second-car accounts priced at **0 < CNY price <= 20**. Prices exactly CNY 20 qualify, and unchanged offers are included again on each subsequent successful refresh. Base/free accounts, other brands, hidden or unavailable offers and stale observations are excluded. Existing bot enablement and QQ price-drop preferences control delivery; there is no new group-broadcast subscription.

Notification checks bypass the cached catalog pointer. A stale snapshot or failed Team query does not suppress previously collected price-change events. QQ reports split by UTF-8 size; exceptionally long links fall back to the catalog rather than sending a broken URL. Telegram display names are bounded before escaping.

Sidrune AI advertising records were verified and updated to `aff=39ZGGP5YA5JR`, retaining each placement's existing promo parameter. This is an authorized data edit, not a schema migration.

No database migration. Deploy the API, importer and five brand frontends from this release using QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. Complete one successful full catalog publication before restoring collection timers.

OpenCodeReview findings were checked against the actual deployment: the API and bundled extensions ship from the same release, so mixed-version private-extension compatibility is outside scope. The CSV and standalone legacy SQLite import tools are not the scheduled production refresh entrypoints. Current-offer freshness is checked at delivery time to avoid advertising expired stock.
