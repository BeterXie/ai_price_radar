# v3.9.84 — Secure framework patch for compact quote cards

Upgrade Next.js from 16.4.3 to 16.4.6 to fix GHSA-mfr8-8qww-v76h, an information disclosure issue involving root parameters, use cache and unstable_cache. This patch resolves the security check that stopped the v3.9.83 production build. Production was not switched to v3.9.83; the current production version remains v3.9.82.

This release includes all v3.9.83 product presentation changes: complete product titles, clearer numeric hierarchy, shorter catalog controls, compact contextual ads beside the filters and in quote details, Claude-only Sidrune targeting and matching compact LLMPort cards for OpenAI.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. Deploy only the clean, published tag after CI succeeds. Pause the three scheduler timers, wait for the current refresh lock, and create one fresh PostgreSQL backup plus source/image rollback points for v3.9.82. Rebuild API, importer and all five frontends. There are no database migrations, crawler/pipeline changes or full refresh gate.

Verify version 3.9.84 in the API and all frontends, five-site health and fixed addresses, the Baidu verification file, logs, shared quote data, desktop/mobile Claude and OpenAI ads, and product detail/shop selection. Restore all timers after validation, then clean temporary deployment/build artifacts while retaining data and v3.9.82 rollback resources.
