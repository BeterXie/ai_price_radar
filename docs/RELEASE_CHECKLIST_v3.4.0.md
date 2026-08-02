# v3.4.0 release checklist

- [ ] Working tree is clean and the release Tag points to the tested commit.
- [ ] `cd apps/api && python -m pytest -q` passes.
- [ ] `cd pipeline && python -m pytest -q` passes.
- [ ] `cd apps/web && npm ci && npm run typecheck && npm run build` passes with production public URLs.
- [ ] Production preflight tests and Compose configuration checks pass.
- [ ] GitHub prompt opens the repository and does not block page interaction.
- [ ] Support dialog switches between WeChat Pay and Alipay, closes with Escape, and works at 390 px width.
- [ ] No payee name is displayed or configured.
- [ ] QR images decode successfully, are not tracked by Git, and are installed only under production `data/support`.
- [ ] Administrator and shop-submission routes do not auto-open community prompts.
- [ ] Rebuild and switch `api` and `web`; do not run a database migration.
- [ ] Tag `v3.4.0` and publish `RELEASE_NOTES_v3.4.0.md` only after CI is green.
