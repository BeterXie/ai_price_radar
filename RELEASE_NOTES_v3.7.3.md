# AI Price Radar v3.7.3 — Product UI and Copy Refinement

This release brings the redesigned Web UI and the follow-up copy/state refinements to the current `main` line.

## What changed

- Unified page hierarchy, catalog surfaces, offer tables, guide layouts, forms, and responsive Web states.
- Rewrote public copy around user decisions: what is being compared, when data was observed, what a state means, and what to do next.
- Separated empty data states from API failures on the public corrections page.
- Clarified that watchlist data is local and Atom readers provide update delivery; the site does not actively push notifications.
- Replaced ambiguous trust-like labels with statistical wording such as “纳入统计” and “信息覆盖”.
- Restored the public “支持作者” footer entry with configurable WeChat Pay and Alipay QR sources.

## Validation

- Web typecheck passed.
- Web test suite passed (54 tests).
- API, Pipeline, Detector, and Crawler CI suites are required before deployment.
- Next.js production build passed with the production API base URL and support configuration.

## Deployment

- No database migration is required.
- Follow `docs/QUICK_DEPLOY.md` and deploy only this release Tag after CI succeeds.
- This is a Web/API release; a full crawler refresh is not a deployment gate.
