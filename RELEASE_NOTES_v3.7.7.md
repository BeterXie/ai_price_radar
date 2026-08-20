# AI Price Radar v3.7.7 — Bounded Crawler Teardown Hotfix

This patch supersedes v3.7.6 before production deployment and closes the remaining refresh stall found by the deployment gate.

## What changed

- Aborts browser-replayed shop API requests at the configured crawler timeout.
- Stops the Playwright connection directly after saving browser state instead of waiting indefinitely for persistent-context closure.
- Removes stale Chromium singleton symlinks before browser refresh startup.
- Allows inventory refreshes one hour to complete scan and atomic publication.
- Aligns release metadata on `3.7.7`.

## Validation

- Crawler self-test and pytest coverage must pass.
- API tests and Web typecheck must pass before tagging.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.7` Tag after CI succeeds.
- Rebuild the Crawler image and complete one full multi-source publication before restoring production timers.
