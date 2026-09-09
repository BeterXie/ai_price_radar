# Release Notes - v3.7.59

## Summary

Release `v3.7.59` optimizes stock status detection and front-end catalog visibility for the 16688 platform:

1. **16688 Platform Unlimited & Recharge Stock Recognition**:
   - In `pipeline/connectors/platform_16688.py`, improved `_stock` detection so that 16688 products with `stock_available_quantity = -1` (or negative quantity) and non-"out" status resolve to `(None, "in_stock")`.
   - On 16688, digital services like 官方秒充, 直充, and CDK use `-1` to represent continuous on-demand supply. Previously, `_integer` filtered out negative numbers, setting stock to `None` and falling back to `unknown`.
   - As a result, 16688 recharge offers were relegated behind all in-stock offers in the public catalog and excluded from lowest-price calculations and "仅看有货" filters. They now properly rank by price and display on the front page.

2. **Idempotent Stock Migration (v12)**:
   - Added `scripts/migrate_16688_stock_status_v12.py` to update existing 16688 offers with `stock_status = 'unknown'` to `in_stock` (in both `offers` and `offer_history`).
   - Covered by unit tests in `scripts/tests/test_migrate_16688_stock_status_v12.py`.

3. **Connector Testing**:
   - Added unit test cases in `pipeline/tests/test_connectors.py` verifying stock resolution for finite in-stock, out-of-stock, and negative/unlimited recharge goods.
