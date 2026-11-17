# v3.9.83 — Compact contextual ads and clearer quote numbers

Keep complete product titles and emphasize prices, inventory, shop counts and real visit counts through color, weight and alignment. Move repeating table ads into compact cards in the quote detail dialog, place the catalog sponsor beside the filters, and reduce the account/recharge filter height.

Show Sidrune only in Claude quote contexts with its customized green creative; keep homepage and relay placements intact. OpenAI's LLMPort card uses the same compact layout. Preserve the shop picker for products with multiple sellers and the existing product detail actions.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. Deploy only a clean published tag with successful CI. Pause the three scheduler timers, wait for the current refresh lock, and create one PostgreSQL backup plus source and image rollback points. Rebuild API, importer and all five frontends from this tag. There are no database migrations or crawler/pipeline changes, so no full refresh gate is required.

Verify API and frontend version 3.9.83, all five sites and fixed container addresses, the Baidu verification file, container health and logs, desktop/mobile Claude and OpenAI cards, and product detail/shop selection behavior. Restore all three timers after verification. Remove only safely reclaimable deployment/build files and cache, retaining current data, the database backup and the previous release's source/image rollback points.
