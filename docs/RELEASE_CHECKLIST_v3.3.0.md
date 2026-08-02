# v3.3.0 release checklist

- [ ] Back up PostgreSQL and verify rollback instructions.
- [ ] Run `migrate_shop_intake_v6.py` twice against a temporary PostgreSQL database and confirm both runs succeed.
- [ ] `cd apps/api && python -m pytest -q` passes.
- [ ] `python -m pytest -q pipeline/tests` passes.
- [ ] Crawler intake tests and Python compilation pass.
- [ ] `cd apps/web && npm ci && npm run typecheck && npm run build` passes.
- [ ] `INTAKE_WORKER_KEY` is at least 32 bytes and differs from `ADMIN_API_KEY`.
- [ ] `SHOP_INTAKE_ADMIN_EMAILS` contains real administrator recipients.
- [ ] `RESEND_API_KEY` and verified `RESEND_FROM` are configured, or the SMTP fallback is complete.
- [ ] Production preflight and Compose configuration checks pass in staging.
- [ ] A test request sends one administrator email and one applicant receipt.
- [ ] Approval and rejection each send the correct applicant result email exactly once.
- [ ] The admin panel shows intake state, failure details, and notification status without exposing credentials.
- [ ] Tag `v3.3.0` and publish `RELEASE_NOTES_v3.3.0.md` only after CI is green.
