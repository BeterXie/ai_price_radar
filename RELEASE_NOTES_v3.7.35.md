# AI Price Radar v3.7.35 Release Notes

**Release Tag**: 3.7.35  
**Date**: 2026-09-04

## Summary

v3.7.35 refines the ChatGPT Plus and SMS verification classifier to eliminate edge-case routing errors where accounts with unverified phone markers (未接马 / 需自行接马) or generic email domains (iCloud, Gmail) were incorrectly placed into chatgpt-access-service (手机接码).

## Key Changes

1. **Precise Account Attribute Filtering**:
   - Expanded without_status stripping in is_chatgpt_service to include 未接马, 需自行接马, 自行接马, 免接马, 未接🐎, and 不接马.
   - Prevented unverified account listings (e.g. 直卡PLUS,未接马，半小时内保首登, G plus/未接马/需自行接马, 多国家PLUS-icloud邮箱-Codex未接马) from false-matching verification service rules.
2. **Removed Email Fallback from Access Service**:
   - Removed legacy GENERIC_EMAIL_MARKERS (Gmail, iCloud) fallback from the chatgpt-access-service classifier rule, ensuring accounts delivered with email domains (e.g. 韩国-PLUS-icloud邮箱-保首登, GP Plus质保25天gmail越南渠道) route to chatgpt-plus.
3. **Team Account Routing**:
   - Added 	eam and 周限额 to implicit brand detection, ensuring 长效周限额team routes to chatgpt-k12.
4. **Delivery Type Precision**:
   - Mapped 未接码 / 未接马 to semi_finished_account (半成品/首登号) with is_comparable=True.
   - Mapped icloud and 保首登 to inished_account (成品号).

## Verification

- pps/api/tests: 246 passed, 3 skipped.
- pipeline/tests: 251 passed.
- pps/web: 55 passed.
