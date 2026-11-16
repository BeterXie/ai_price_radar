# v3.9.82 — Compact actions for the Astra comparison

Style the comparison's sample links and article links as small black buttons, including the model registration link. This completes the requested link treatment without changing shared Markdown rendering or other articles.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. Rebuild API, importer and all five frontends from the clean CI-passing tag. There are no migrations or crawler/pipeline changes and no full refresh gate. Preserve the already paused schedules from the v3.9.81 rollout, create a fresh v3.9.81 database/source/image rollback point, verify production health and logs, then confirm both animations and compact buttons on desktop and mobile before restoring the original schedules. Article 114's content was already updated successfully in v3.9.81 and must not be rewritten again.
