# v3.9.58 — Sponsor placements

The homepage now displays configured sponsors in place of the first three relay-directory entries. Sort order selects the primary card; enabled state and schedules remain managed in the advertising panel. The relay page has independent sponsor banners, with Sidrune first and auto-code second. auto-code uses its supplied blue logo and a compact blue treatment; it is not placed on the homepage or in Claude offers.

Claude brand and product pages support `claude_feed` and `claude_detail`. One compact advertisement appears after the fifth offer (or the last when fewer exist). Opening an offer moves the advertisement below its shop quotes, ahead of the purchase guide. Multiple offers can stay open; only the most recently opened one receives the detail advertisement. Closing it returns the advertisement to another open offer, or to the list. Existing offer sorting, pricing, and monitoring data are unchanged. Each position keeps its own ad record and click counter.

No database migration is required. Rebuild API, Web and importer following `docs/QUICK_DEPLOY.md`.

## Campaign configuration

- Sidrune homepage: `https://cn.sidrune.ai/register?promo=PRICEMEMO_HOME7&aff=46UNX83LB7VV`.
- Sidrune relay banner: `https://cn.sidrune.ai/register?promo=PRICEMEMO_TOP30&aff=46UNX83LB7VV`.
- Sidrune Claude inline positions: `https://cn.sidrune.ai/register?promo=PRICEMEMO_HOME7&aff=46UNX83LB7VV`, sharing the homepage promo as requested. Their local click counters remain separate.
- Display Sidrune immediately; billing starts 2026-11-11 12:00 Asia/Shanghai. Homepage ends 2026-11-18 12:00, relay banner and inline campaign end 2026-12-11 12:00. Store UTC end timestamps and leave the display start unset for the free preview period.
- auto-code: relay banner position 2, `https://vip.auto-code.net/register?aff=857AH6YV3UU3`, enabled immediately. No end date was supplied; leave it unset until specified.
- Retain LLMPort as a secondary homepage sponsor and its existing catalog advertisement. Do not create a Sidrune or auto-code monitoring-directory record as part of advertising configuration.
- Sidrune's 0.25–4.5x is a group billing multiplier, not a discount against official USD prices. auto-code integration wording follows its public usage guide; no performance or uptime guarantees are added.

## Validation

- API tests: 1,231 passed, 5 skipped; campaign ordering, separate links and expiration boundaries covered.
- Web tests: 166 passed, including multi-sponsor rendering, disclosures and Claude targeting.
- Typecheck and production standalone build required before release.
- Browser checks cover compact inline sizing, independent expanded rows, preserved purchase guides, distinct campaign links, brand targeting and responsive layouts.
