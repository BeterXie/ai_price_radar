# AI Price Radar v3.7.34 Release Notes

**Release Tag**: `v3.7.34`  
**Date**: 2026-09-04

## Summary

v3.7.34 merges the `Codex` category into `ChatGPT Plus` and other appropriate underlying tiers (Go, Team, Free), establishes a clear, dedicated `手机接码` (SMS Verification) category, and refines the classifier to correctly distinguish account attributes (`已接码`, `已接马`) from independent verification services.

## Key Changes

1. **Codex -> Plus & Underlying Tiers**:
   - Removed the top-level prefix interceptor that forced all items mentioning `codex` into `codex-access`.
   - Accounts such as `【源头】8.31新 codex plus账号 已接马【带rt】，sub2 CPA格式` and `Codex 账号独享` now correctly classify as `chatgpt-plus` (with `finished_account` or `session_token` delivery type).
   - `Codex Go` items route to `chatgpt-go`.
   - `Codex Team` items route to `chatgpt-k12`.
   - `Codex Free` items route to `chatgpt-account`.
   - Added `已接码`, `带RT`, `Sub2API`, and `Codex` tags to `TAG_RULES`.
2. **Dedicated "手机接码" Category**:
   - Differentiated account attribute markers (`已接码`, `已接马`, `已绑手机`) from independent verification services (`代接码`, `手机接码`, `实卡接码`, `接码卡密`).
   - Allowed SMS verification services through classifier and renamed public frontend tab `辅助服务` to `手机接码`.
   - Removed the standalone `Codex` tab from the OpenAI navigation header.
3. **Synchronization**:
   - Synchronized classifier, delivery type detection, tag extraction, and product seed definitions between `apps/api` and `pipeline`.

## Verification

- `apps/api/tests`: 233 passed, 3 skipped.
- `pipeline/tests`: 111 passed.
- `apps/web`: 55 passed.
