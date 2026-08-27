# AI Price Radar v3.7.15 — 16688 Egress Connectivity Fix

This patch fixes validated 16688 source access from the isolated detector network when DNS returns an unreachable IPv6 address before a reachable IPv4 address.

## What changed

- Caches every validated public address returned for a source hostname during a detection run.
- Retries another validated address only after a socket-level connection error, then pins the successful address for later requests.
- Retains the existing single-resolution behavior, public-IP validation, and TLS hostname verification.

## Impact

- Retrying a submitted 16688 shop can now progress through source detection on the production network.
- Shop approval and publication remain manual; `16688` appears in the public catalog source filter only after a reviewed shop has published public offers.

## Validation

- HTTP client and platform probe regression tests cover IPv6-unreachable, IPv4-successful fallback and address pinning.
- API, detector, pipeline, and Web release gates must pass in CI.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only the `v3.7.15` tag after CI succeeds.
- No database migration is required.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler` because the shared HTTP client changed.
