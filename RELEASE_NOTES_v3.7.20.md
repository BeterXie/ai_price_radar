# AI Price Radar v3.7.20 - Intake Result Idempotency

This maintenance release removes false intake-result failures observed during production crawler refreshes.

## What changed

- The crawler records the intake attempt whose result has already been accepted, so later scans do not re-report that completed attempt.
- The internal intake API treats a retry for the same closed attempt as idempotent. It does not accept results from a different attempt.
- The atomic multi-source publisher now performs LDXP onboarding after its snapshot commits, using only public offers from that snapshot and the matching validated attempt.

## Validation

- Crawler state tests cover reporting an attempt once and resetting that marker when a new claim is received.
- API tests cover closed-attempt retry behavior and rejection of a different attempt.
- Pipeline tests cover post-publication onboarding and ensure completed applications are not re-onboarded.

## Deployment

- No PostgreSQL migration is required. Rebuild the API, crawler, and importer from the `v3.7.20` tag, then complete one full refresh before restoring timers.
