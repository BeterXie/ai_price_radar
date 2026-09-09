# Release Notes - v3.7.58

## Summary

Release `v3.7.58` consolidates ChatGPT Pro product tiers across the entire platform:
1. **Frontend UI**: Removed generic `chatgpt-pro` tab from `PRODUCT_TABS.OpenAI` in `apps/web/lib/catalog.ts`. Navigation now exclusively features **Pro 5x** (`chatgpt-pro-5x`) and **Pro 20x** (`chatgpt-pro-20x`).
2. **Classifier Precision**: Upgraded `_pro_multiplier` in `apps/api/app/services/classifier.py` and `pipeline/common.py` to recognize Chinese market dollar designations (`100刀` -> 5x, `200刀` -> 20x) and resolve lookahead failures with composite expressions (e.g. `20x 200刀`). Eliminated generic `chatgpt-pro` returns so all future crawled/imported Pro items automatically classify into Pro 5x or Pro 20x.
3. **Product Visibility**: Automatically set `is_visible = False` on legacy `chatgpt-pro` product in `apps/api/app/seed.py` and `pipeline/common.py`.
4. **Data Migration**: Added `scripts/reclassify_pro_offers.py` to reclassify existing production offers from `chatgpt-pro` into either `chatgpt-pro-5x` or `chatgpt-pro-20x`.

## Verification

- `pipeline/tests`: 332 passed
- `apps/api/tests`: 342 passed
- `apps/web`: 63 unit tests passed, Next.js production build succeeded with 0 errors
