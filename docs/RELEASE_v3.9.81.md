# v3.9.81 — Two Astra pelican animations

The GPT-6.2 article can show the original GPT-6 Astra animation alongside the new sample before its body. Both use the existing sandboxed viewer, keep independent playback controls and offer a direct full-page link. The comparison stacks on small screens and is selectable in the article editor.

Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md. Rebuild API, importer and all five frontends from the clean release tag after CI. There are no database migrations, crawler or pipeline changes; a full refresh is not required. Create a fresh backup and rollback point from v3.9.80, validate the public sites and logs, then update article 114 using the admin content API with a saved before-state. Preserve the title, slug, visibility and final LLMPort registration link. Verify both animations and the rewritten article before restoring schedules.
