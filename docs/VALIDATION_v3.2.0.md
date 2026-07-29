# v3.2.0 validation report

Validation date: 2026-07-29

Source archive SHA-256: `F18E4D2812E9C9DFC51BF14DF383672780D8A9E3D43410275A24D54A3BCE364B`

## Passed in the release checkout

- API suite: `105 passed`.
- Pipeline suite: `78 passed`.
- Python bytecode compilation for API, pipeline, connectors, migration and release scripts.
- JSON parsing for `package.json` and `package-lock.json`.
- GitHub Actions workflow YAML parsing.
- Version consistency across `VERSION`, API, Web package and lock file: `3.2.0`.
- `npm ci` completed from the canonical public npm lock URLs.
- TypeScript project check: `tsc --noEmit` passed.
- Next.js 15.5.21 production build passed and generated 15 static/dynamic pages.
- Local production-server smoke passed for the homepage, catalog, product detail, methodology, about, privacy, terms, security, developers, corrections, watchlist and merchant submission pages.
- Browser-local watch state and target-price changes updated the generated Atom Feed URL.
- Atom XML, Sitemap, OpenAPI additions and merchant Feed public/private URL handling passed HTTP smoke checks.
- v5 migration rehearsal passed against an isolated PostgreSQL 16 database.
- The v5 migration was applied twice successfully; all three columns, the index and resolved-report backfill were verified.

## Corrected during acceptance

- Merchant JSON local-file loading treated Windows drive letters as URL schemes. Local files are now detected before HTTPS URL validation; remote feeds still require public HTTPS targets and retain the SSRF, redirect, content-type and size protections.
- The first Pipeline CI run lacked `pytest` because production requirements intentionally contain runtime dependencies only. CI now installs `pipeline/requirements-test.txt`, which layers the pinned test dependency over runtime requirements.
- The generic release checklist title was synchronized to `AI Price Radar v3.2.0 — Productization & Evidence`.
- The production quick-deploy runbook now requires migration rehearsal and runs required migrations with the newly built API image before switching containers.

## Remaining release gates

- Push `release/v3.2.0` and require the GitHub Actions API, Pipeline and Web jobs to pass on the release commit.
- Do not create `v3.2.0` until those checks are green.
- Before production deployment, create and verify a PostgreSQL backup.
- During deployment, apply `scripts/migrate_productization_v5.py` before switching API/Web, then repeat the production health and public-data smoke checks.
