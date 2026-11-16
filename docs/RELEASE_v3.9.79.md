# v3.9.79 — Compact purchase controls and pelican article

The primary catalog's three actions use small dark buttons matching the existing selected filter. Ordering is 32px high; comparison and details are 28px. The group is bounded to 144px with 6px gaps. Existing merchant selection, details dialogs, keyboard focus and click behavior are retained.

This rollout also includes v3.9.78, which was tagged but never switched into production: disable unused catalog/shop prefetch, add the supplied GPT-6.2 Astra pelican demo, and use a taller mobile article iframe. Publish the requested model PK article after verifying the live sandboxed animation, then validate desktop/mobile controls and the original LLMPort registration link.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. No migrations or crawler/pipeline changes; no full refresh is required. Use the already prepared rollback point `20261116_222039`, created while v3.9.77 remained active, and preserve its single database backup. The v3.9.77 runtime failure evidence remains recorded; v3.9.79 must pass post-switch logs and health checks before restoring the original active schedules.
