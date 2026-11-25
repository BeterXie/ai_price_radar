# v3.9.112 — Default Clarity analytics

Connects `ai.pricememo.cn` to Clarity project `zj9ygr64oc` for visits, heatmaps and session recordings by default. The Clarity consent popup is removed. Baidu's existing preference and campaign attribution are preserved; separately configured Google Analytics keeps its own consent flow.

Private pages reload into a document without Clarity before their UI can render; login dialogs and account nicknames are masked. Local, preview, apex-alias and other brand visits do not load this project's tag.

This patch is based on the deployed v3.9.111 application. It does not include collector changes. No database migrations or collection changes are required. Preserve the deployed COLLECTOR_RELEASE and remote worker configuration.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md: build and package all five frontends, rebuild API and importer, preserve backups and existing data, and verify the same application version across all sites. If the live proxy has a CSP, merge the Clarity allowances into that site's policy without replacing unrelated proxy routes.

Validation: API suite, Web typecheck/tests, CI, production frontend builds, staging preflight, default loading checks and Clarity collection requests.
