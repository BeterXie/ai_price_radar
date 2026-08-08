# AI Price Radar v3.7.4 — Button Contrast Hotfix

This patch fixes a CSS cascade issue that caused text and icons on dark action buttons to inherit the page text color.

## What changed

- Scoped the native form-control reset to Tailwind's base layer so utility classes such as `text-white` can apply correctly.
- Bumped the release version to `3.7.4` so the public health endpoint, API metadata, and Web package identify the deployed build consistently.

## Validation

- Web typecheck passed.
- Web production build passed with the production API base URL and support configuration.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only this release Tag after CI succeeds.
- This is a Web/API release; a full crawler refresh is not a deployment gate.
