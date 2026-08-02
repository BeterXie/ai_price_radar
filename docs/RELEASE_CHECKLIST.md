# Release checklist

## Before tagging

- [ ] `python -m pytest -q` passes in `apps/api`.
- [ ] `npm ci`, `npm run typecheck`, and `npm run build` pass in `apps/web`.
- [ ] Homepage no longer promotes sub-¥1 offers as the trusted minimum.
- [ ] A product with normal offers and one anomaly returns the normal trusted minimum.
- [ ] `related_lowest_price` still exposes the raw all-in-stock minimum.
- [ ] API OpenAPI schema includes `trusted_offer_count`, `median_price`, and `is_trusted_price`.
- [ ] Shop-intake submission, approval, rejection, retry, and notification tests pass.
- [ ] `migrate_shop_intake_v6.py` succeeds twice against a temporary PostgreSQL database.
- [ ] `INTAKE_WORKER_KEY` differs from `ADMIN_API_KEY`.
- [ ] Production has real `SHOP_INTAKE_ADMIN_EMAILS`, `RESEND_API_KEY`, and verified `RESEND_FROM` values, or a complete SMTP fallback configuration.
- [ ] Author-support QR images exist only in production `data/support`, return `image/jpeg`, and are not tracked by Git.
- [ ] GitHub and author-support prompts do not auto-open on administrator or shop-submission routes.
- [ ] Production database backup is current.
- [ ] Staging smoke test covers homepage, catalog, product detail, grouped offers, reports, and admin login.

## Publish

```powershell
git tag -a v3.4.0 -m "AI Price Radar v3.4.0 — Community & Support"
git push origin v3.4.0
```

Create a GitHub Release from `v3.4.0` using `RELEASE_NOTES_v3.4.0.md`.

## After publishing

- [ ] Verify the release archive.
- [ ] Verify CI on the release commit.
- [ ] Deploy the same commit SHA.
- [ ] Confirm production health and restored timers; require a full refresh only for crawler, pipeline, or database changes.
- [ ] Check logs for schema or serialization errors.
