# AI Price Radar v3.7.30 Release Notes

**Release Tag**: `v3.7.30`  
**Date**: 2026-09-03

## Summary

v3.7.30 upgrades the product classification and catalog protection engine in both the FastAPI service and the data ingestion pipeline. It addresses title ambiguities by using product detail descriptions, strictly excludes non-products, isolates reverse-proxy only tokens, filters multi-user pools, and protects standard tier integrity.

## Key Changes

1. **Detail-Driven Classification**:
   - When storefront titles are cryptic or abbreviated (e.g. `【特惠秒发】独享个人月度会员`), the classifier inspects `raw_products.raw_json->>'description'` for explicit brand indicators (`chatgpt plus`, `claude pro`, `gemini advanced`, `super grok`, `x premium`, `codex`).
2. **Universal Non-Product Exclusion**:
   - Systematically rejects pure tutorials (`保姆教程`, `图文教程`, `反代教程`), test items (`测试商品`, `不要拍`), SMS verification ad services (`接码渠道`), virtual cards (`0刀卡`, `虚拟卡`), and referral boost links from standard subscription products.
3. **Reverse Proxy / Sub2API Token Isolation**:
   - Offers with reverse-proxy-only / no account credentials (`只能反代`, `无账号密码`) are routed to `codex-access` (`session_token`) rather than `chatgpt-plus`.
4. **Pro & Multiplier Integrity**:
   - Team sub-accounts (`Team bug 子号`) and API quotas (`20X 额度｜50美金`) are filtered out of `chatgpt-pro` and `chatgpt-pro-20x`.
5. **Shared Carpool Pool Isolation**:
   - Expanded `SHARED_POOL_MARKERS` to catch `拼车`, `共享账号`, `多人共享`, `车位`, setting `delivery_type = 'shared_pool'` and `is_comparable = false`.
6. **Storefront Category Fix**:
   - Storefront categories ending in `分组` (e.g. `Grok分组`) no longer cause genuine subscriptions to be falsely rejected.

## Verification

- `apps/api/tests`: 221 passed, 3 skipped.
- `pipeline/tests`: 238 passed.
- `apps/web`: `npm run build` compiled all 64 pages cleanly.
