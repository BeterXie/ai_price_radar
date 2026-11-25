# v3.9.111 — Microsoft Clarity

Connects `ai.pricememo.cn` to Clarity project `zj9ygr64oc` for visits, heatmaps and session recordings after visitors explicitly allow analytics. Previous Baidu/Google permission does not grant Clarity permission. Baidu's existing preference and campaign attribution are preserved.

Private pages reload into a document without Clarity before their UI can render; login dialogs and account nicknames are masked. Local, preview, apex-alias and other brand visits do not load this project's tag.

This production patch is based on v3.9.109. It does not include v3.9.110's independent collector proxy changes. No database migrations or collection changes are required. Preserve the deployed COLLECTOR_RELEASE and remote worker configuration.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md: build and package all five frontends, rebuild API and importer, preserve backups and existing data, and verify the same application version across all sites. If the live proxy has a CSP, merge the Clarity allowances into that site's policy without replacing unrelated proxy routes.

Validation: API suite, Web typecheck/tests, CI, production frontend builds, staging preflight, live consent gating and Clarity collection requests.
