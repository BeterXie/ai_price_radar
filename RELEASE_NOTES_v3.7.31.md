# AI Price Radar v3.7.31 Release Notes

**Release Tag**: `v3.7.31`  
**Date**: 2026-09-04

## Summary

v3.7.31 fixes shop intake approval and platform detection for storefronts using `wzyp.cn`, and equips the admin console with tools to change platform types, trigger re-detection, and approve previously un-approvable intakes.

## Key Changes

1. **Source Detector Coverage**:
   - Added `wzyp.cn` and `www.wzyp.cn` to `LDXP_HOSTS` in `detector/probe.py`. New store intake applications under `wzyp.cn` are now correctly detected as `ldxp` (链动小铺) instead of falling back to `other` (其他独立站).
2. **Admin Platform Modification**:
   - Added `POST /api/v1/admin/source-intakes/{id}/platform` and an inline platform selector dropdown on every shop intake card in `/admin`, enabling admins to override an intake's platform type directly.
3. **On-Demand Re-Detection**:
   - Added `POST /api/v1/admin/source-intakes/{id}/redetect` with a "重新检测" button in the admin interface, allowing admins to re-run detection against the latest platform rules at any time.
4. **Resilient Intake Approval**:
   - Enhanced `POST /api/v1/admin/source-intakes/{id}/approve` so that if an intake was marked `other` but matches a known platform (e.g. `wzyp.cn`), it auto-promotes to `ldxp` and queues for worker validation rather than throwing a 409 error.
   - Restored the "批准" button in the admin console for all pending intakes.

## Verification

- `apps/api/tests`: 223 passed, 3 skipped.
- `detector/tests`: 68 passed, 1 skipped.
- `pipeline/tests`: 238 passed.
- `apps/web`: `npm run typecheck` and `npm test` passed 55/55 tests.
