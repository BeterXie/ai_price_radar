# Release checklist

## Before tagging

- [ ] `python -m pytest -q` passes in `apps/api`.
- [ ] `npm ci`, `npm run typecheck`, and `npm run build` pass in `apps/web`.
- [ ] Homepage no longer promotes sub-¥1 offers as the trusted minimum.
- [ ] A product with normal offers and one anomaly returns the normal trusted minimum.
- [ ] `related_lowest_price` still exposes the raw all-in-stock minimum.
- [ ] API OpenAPI schema includes `trusted_offer_count`, `median_price`, and `is_trusted_price`.
- [ ] Production database backup is current.
- [ ] Staging smoke test covers homepage, catalog, product detail, grouped offers, reports, and admin login.

## Publish

```bash
git tag -a v3.1.0 -m "AI Price Radar v3.1.0 — Trusted Pricing"
git push origin v3.1.0
```

Create a GitHub Release from `v3.1.0` using `RELEASE_NOTES_v3.1.0.md`.

## After publishing

- [ ] Verify the release archive.
- [ ] Verify CI on the release commit.
- [ ] Deploy the same commit SHA.
- [ ] Confirm production health and one full data refresh.
- [ ] Check logs for schema or serialization errors.
