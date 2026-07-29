# v3.2.0 release checklist

- [ ] Back up PostgreSQL and verify restore instructions.
- [ ] Run `migrate_catalog_v4.py` if required, then `migrate_productization_v5.py`.
- [ ] `cd apps/api && python -m pytest -q` passes.
- [ ] `python -m pytest -q pipeline/tests` passes.
- [ ] `cd apps/web && npm ci && npm run typecheck && npm run build` passes.
- [ ] Confirm official-reference links and `checked_at` dates.
- [ ] Confirm `/methodology`, `/privacy`, `/terms`, `/security`, `/developers`, `/corrections`, and `/watchlist` render.
- [ ] Confirm public correction API never exposes raw message or contact fields.
- [ ] Confirm merchant Feed validation rejects local/private targets.
- [ ] Smoke-test production API, Sitemap, Atom Feed and source links.
- [ ] Tag `v3.2.0` and publish `RELEASE_NOTES_v3.2.0.md`.
