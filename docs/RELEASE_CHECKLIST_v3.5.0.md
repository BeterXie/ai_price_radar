# v3.5.0 release checklist

- [ ] Working tree is clean and Tag `v3.5.0` points to the tested `main` commit.
- [ ] API, Pipeline, Detector, Crawler, Scripts, and Web validation pass.
- [ ] PostgreSQL 16 migration rehearsal succeeds twice without skips.
- [ ] Detector and Importer images build and import `price_radar_http` from the same source commit.
- [ ] Base and production Compose configurations validate.
- [ ] Production timers are stopped and the current refresh lock is released before backup.
- [ ] One PostgreSQL backup, the pre-deploy source archive, and rollback image tags are created.
- [ ] Staging preflight and SHA-256 verification pass before replacing production source.
- [ ] Detector has no database credentials, Redis credentials, Docker socket, or default/frontend network membership.
- [ ] Production egress enforcement permits Detector traffic only to public TCP/443 destinations.
- [ ] v5, v6, v7, and v8 migrations run successfully before the API switch.
- [ ] API reports version `3.5.0`; Web, API, DB, and source-detector are healthy.
- [ ] A complete multi-source publication succeeds using `ai-price-radar-importer`.
- [ ] Published sources survive a second refresh and disabled sources leave the next snapshot.
- [ ] Homepage, catalog, product detail, shop page, intake flow, and administrator review flow pass smoke testing.
- [ ] All three production timers are restored and deployment logs contain no traceback, exception, or critical errors.
- [ ] Publish `RELEASE_NOTES_v3.5.0.md` only after the `main` CI run is green.
