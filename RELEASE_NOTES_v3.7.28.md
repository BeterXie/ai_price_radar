# AI Price Radar v3.7.28 - WZYP Storefront Support and KFLA Shop Intake

## What changed

- Extended LDXP source platform detection to support `wzyp.cn` and `www.wzyp.cn` hostnames alongside legacy `pay.ldxp.cn` / `ldxp.cn`.
- Updated crawler URL parsing and input normalization to recognize and extract `wzyp.cn/shop/*` URLs.
- Added `https://wzyp.cn/shop/KFLA` to general and crawler seed lists, and recorded candidate in crawler database.
- Updated source intake hints in web app to reference `wzyp.cn` alongside `pay.ldxp.cn`.

## Safety and data scope

- Preserves `token.casefold()` as `source_key` and `token` as `shop_token` under the existing `ldxp` platform namespace to prevent shop identity collisions.
- No database schema migration is required.

## Validation

- API source detection unit tests cover `https://wzyp.cn/shop/KFLA` and legacy `pay.ldxp.cn` paths.
- Crawler self-test and pytest suites verify extraction and normalization of `wzyp.cn` shop URLs.
- Web client validation tests verify `https://wzyp.cn/shop/KFLA` acceptance.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.28` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.
- No full crawler refresh or database migration is required for this release.
