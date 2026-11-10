# v3.9.59 — Sponsor release packaging

Includes the sponsor placements and campaign configuration documented in `RELEASE_v3.9.58.md`. The first production build stopped before container switching after including the host's accumulated public snapshot history in the Web build context. Production remained on v3.9.57.

Exclude `apps/web/public/data` from the Web Docker context. Production Compose already mounts that directory at `/app/public/data`; the running website still serves the same snapshots. This prevents duplicating gigabytes of published history into each new Web image. Sponsor artwork and the Baidu verification file remain included.

No database migration. Follow `docs/QUICK_DEPLOY.md`, rebuilding API, Web and importer from this tag. Keep the previously prepared database/source/image rollback point while completing this release attempt; no containers were switched and no campaign configuration was written by the earlier attempt.

Validation: full API and Web tests, production typecheck/build, and CI container builds. All sponsor layout, targeting, tracking and schedule checks from v3.9.58 apply unchanged.
