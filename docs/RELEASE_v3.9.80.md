# v3.9.80 — Compact product actions and pelican article

Show ordering, same-item comparison and product details as compact black buttons. Include the supplied pelican animation before the model PK article body and reduce speculative catalog prefetch.

The v3.9.79 API still reported 3.9.77 and failed the production version gate. Its API container was automatically rolled back before any web switch. This release aligns API, root and web versions and changes the existing API version test to compare those sources directly.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. No migration or crawler/pipeline changes; no full refresh is required. Reuse rollback point `20261116_222039` and its existing database backup after verifying the v3.9.77 baseline. Preserve the failed v3.9.79 attempt evidence. Rebuild API, importer and five frontends from this clean tag; check image API version before switching, then complete normal version, page, runtime and article checks before restoring schedules.
