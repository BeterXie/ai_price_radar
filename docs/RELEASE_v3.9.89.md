# v3.9.89

Catalog quote pages now load full merchant details only for the requested page. Price statistics and details share one SQL statement so a concurrent snapshot publication cannot turn the page empty. Product cards, product summaries and quote groups use compact statistics instead of thousands of ORM objects. Existing prices, trust calculations, filters, grouping and ordering are preserved.

OpenAI Team snapshot alerts now include explicitly identified head cars priced at or below CNY 30; other qualifying Team offers retain the inclusive CNY 20 limit. Titles must contain an unambiguous end time later than the send-time check. Beijing dates, Chinese clock values and overnight wording resolve against the offer's observation time so stale relative titles do not become future offers each day. Alerts show the resolved end time and keep exact PriceMemo offer links. Products with unknown end times are omitted.

The production availability check recognizes container OOM events and reports public snapshots older than two hours. Existing memory admission thresholds and public API concurrency settings stay in place.

Validation includes bounded detail loading, unchanged price trust across pages, a publication race regression, title/date and inclusive price boundaries, and expired alerts during delivery. A read-only comparison against a real production snapshot matched 41 public response cases across quote pages, groups, product cards, details and recommendations.

In a constrained Python 3.13 production-image experiment, the final quote-page implementation reduced tracked Python allocation peak from 100.33 MiB to 10.69 MiB and process high-water RSS from 288.09 MiB to 103.86 MiB. A separate 256 MiB container completed 58 mixed read requests at concurrency 1/4/8/15 without failures, reaching 225.28 MiB RSS at 15 concurrency. These measurements exclude other API background tasks and do not replace post-deployment observation.

No database migration or pipeline/crawler changes. Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md for a clean published tag, passing CI, backups, preflight, API/importer and five frontend builds. Existing upstream certificate and 16688 connectivity incidents remain independent of this release.
