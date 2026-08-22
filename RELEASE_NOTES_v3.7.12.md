# AI Price Radar v3.7.12 — Per-Shop Browser Watchdog

This patch prevents one wedged Chromium page from holding the production refresh lock for hours.

## What changed

- Runs browser scanning in a supervised child process.
- Applies a 120-second wall-clock deadline to every production shop scan.
- Terminates the full Worker and Chromium process group after a timeout, records that shop as a transient network failure, and restarts the browser for the next shop.
- Keeps the existing navigation, browser API request, profile cleanup, teardown, and compact publication safeguards.
- Aligns release metadata on `3.7.12`.

## Validation

- A deterministic hanging Worker must time out and be terminated.
- The next shop must complete through a newly started Worker.
- Crawler self-tests and the full API, crawler, pipeline, and Web gates must pass.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.12` Tag after CI succeeds.
- Keep the hourly refresh timer paused until one complete production scan and publication succeeds with the new Crawler image.
