# v3.9.78 — Pelican demo and catalog prefetch reduction

Catalog and shop links no longer prefetch pages before a visitor chooses them. During v3.9.77 acceptance, the main site received 553 Next.js prefetch requests in six minutes, alongside a burst that exhausted the API's bounded database pool. This change removes the speculative fan-out from product filters, quote rows, merchant rows and homepage product lists. Normal link clicks retain Next.js navigation. Pool limits and request deadlines remain bounded.

Add the owner's supplied `pelican-ride.html` unchanged as `/demos/benchmarks/pelican-gpt62-astra.html`. The article uses the existing `demo_type=iframe` path, rendered before Markdown with `sandbox=allow-scripts`. Its mobile viewport is portrait-shaped so the artwork and playback control fit. No external scripts, network calls or storage access are present in the supplied demo.

Publish “gpt-6.2模型发布，最新鹈鹕测试” under `/skills` as model PK content after the asset and viewer pass production checks. Review observable artwork and motion, compare with the existing pelican article, and preserve the requested LLMPort registration link. Do not invent official release details, generation settings or benchmark scores.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md: full API checks, clean published tag with successful exact-commit CI, database/source/image rollback points, staging preflight, API/importer and five frontend builds. No migration or full crawler refresh is required. Keep the failed v3.9.77 log evidence; this release must pass fresh post-switch logs and availability checks. Restore the original active schedules only after acceptance, and record that v3.9.78 supersedes the incomplete v3.9.77 release.
