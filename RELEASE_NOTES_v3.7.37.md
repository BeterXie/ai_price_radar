# AI Price Radar v3.7.37 Release Notes

**Release Tag**: v3.7.37  
**Date**: 2026-09-04

## Summary

v3.7.37 adds erification_service (接码验证辅助服务) to COMPARABLE_DELIVERY_TYPES, ensuring that products in the dedicated chatgpt-access-service (ChatGPT 手机接码) category participate in comparable pricing calculations (is_comparable=True) and display cleanly on the product page.

## Key Changes

1. **Comparable Delivery Types for Verification Services**:
   - Added "verification_service" to COMPARABLE_DELIVERY_TYPES in both pps/api/app/services/classifier.py and pipeline/common.py.
   - Offers categorized under chatgpt-access-service now have is_comparable=True and populate the default comparable=true catalog view, resolving the empty state on /products/chatgpt-access-service.
2. **Database Reclassification for Verification Services**:
   - Updated all active offers with delivery_type = 'verification_service' to is_comparable = true.

## Verification

- pps/api/tests: 250 passed, 3 skipped.
- pipeline/tests: 255 passed.
- pps/web: 55 passed.
