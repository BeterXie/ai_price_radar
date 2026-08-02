# v3.3.1 release checklist

- [ ] Working tree is clean and the release Tag points to the tested commit.
- [ ] `cd apps/api && python -m pytest -q` passes.
- [ ] `cd pipeline && python -m pytest -q` passes.
- [ ] `cd apps/web && npm ci && npm run typecheck && npm run build` passes.
- [ ] Administrator submission email contains `/admin?intake=<id>#source-intake-<id>` and no administrator key.
- [ ] The admin link still requires the administrator key and highlights the referenced intake after loading.
- [ ] Final onboarding email contains the published `/shops/<token>` URL.
- [ ] Production preflight and Compose configuration checks pass.
- [ ] Rebuild and switch `api`, `web`, and `notification-worker`; no database migration is required.
- [ ] Tag `v3.3.1` and publish `RELEASE_NOTES_v3.3.1.md` only after CI is green.
