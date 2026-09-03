# AI Price Radar v3.7.32 Release Notes

**Release Tag**: `v3.7.32`  
**Date**: 2026-09-04

## Summary

v3.7.32 implements automatic shop intake approval and administrator email notifications. Once a merchant or user submits a shop URL and the isolated security detector confirms a valid platform, the request is automatically approved and queued for product validation, with an automated notification dispatched to the administrator.

## Key Changes

1. **Automatic Shop Intake Approval**:
   - Added configuration `SHOP_INTAKE_AUTO_APPROVE` (configured to `true` in production).
   - In `apps/api/app/routers/internal.py`, when detection reports a valid supported platform (`ldxp`, `dujiao_next`, `woocommerce`, `16688`, `merchant_json`, `schema_org`), the intake immediately transitions to `queued` (for `ldxp`) or `approved` (for catalog publication) without waiting for manual admin approval.
2. **Administrator & Applicant Notifications**:
   - Enqueues `shop_request.auto_approved.admin` email notification to all emails configured in `SHOP_INTAKE_ADMIN_EMAILS`, containing the store URL, detected platform, shop name, contact email, and direct link to the admin dashboard.
   - Enqueues `shop_request.approved` to the applicant with updated status guidance.
3. **Safety Boundaries**:
   - `other` independent storefronts and unrecognized platforms continue to pause in `pending_review` for human review.
   - Already published/onboarded stores are never downgraded by re-detections or duplicate submissions.

## Verification

- `apps/api/tests`: 225 passed, 3 skipped (including comprehensive auto-approval tests).
- `detector/tests`: 68 passed, 1 skipped.
- `pipeline/tests`: 238 passed.
- `apps/web`: 55 passed.
