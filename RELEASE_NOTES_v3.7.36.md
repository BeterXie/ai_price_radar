# AI Price Radar v3.7.36 Release Notes

**Release Tag**: v3.7.36  
**Date**: 2026-09-04

## Summary

v3.7.36 includes session_token (reverse proxy tokens / 仅反代 / 无账号密码) into COMPARABLE_DELIVERY_TYPES, allowing reverse-proxy accounts to participate in benchmark price calculations (is_comparable=True) alongside finished and semi-finished accounts.

## Key Changes

1. **Comparable Delivery Types Expansion**:
   - Added "session_token" to COMPARABLE_DELIVERY_TYPES in both pps/api/app/services/classifier.py and pipeline/common.py.
   - Offers offering reverse proxy tokens (such as 【自营】Plus 已接马 仅反代，发CDK 不可网页 不可囤) now have is_comparable=True.
2. **Test Expectations Updated**:
   - Updated classifier test cases across API and Pipeline test suites to expect is_comparable=True for session_token items.

## Verification

- pps/api/tests: 246 passed, 3 skipped.
- pipeline/tests: 251 passed.
- pps/web: 55 passed.
