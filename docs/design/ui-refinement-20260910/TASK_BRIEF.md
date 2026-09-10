# UI refinement — 2026-09-10

## Authority and scope
- Current request: 使用 victor-design-system「对本项目的UI进行一次升级优化」。
- Existing approved foundation: `../site-ui-refresh/DESIGN_CONTROL.md` records explicit approval of Signal Ledger r2 and production React/TypeScript/CSS delivery on 2026-08-22. This is project-recorded evidence, not a new approval in this conversation.
- Form: incremental changes to the working Next.js product; no new brand direction, Figma handoff, generated imagery, backend changes or deployment.
- Scope: home, catalog/product shared filters, product overview rows and inherited UI tokens. Preserve all existing routes, pricing semantics, source attribution, inventory and risk disclosures.
- Interaction policy: follow the approved foundation; new visual directions or broad page-family redesigns require a new user decision. Do not claim user approval of this iteration.

## Reader, material and form
- Reader action: find a product, narrow comparable offers, inspect delivery and source, then verify the original listing.
- Viewing conditions: desktop and phone; compare default, dense, expanded-filter and recovery states.
- No attached image. Existing logo/platform icons are identity assets; no new hero image is needed.
- Source chain: local source and approved renders → read-only live product audit. No missing visual-asset role, web assets or generation.
- Mother relation: each observed price belongs to a product, stock status, source and observation time. Preserve this relationship after removing decorative headings.
- Required truth: observed prices are not guarantees; unknown warranty/delivery remains unknown; current metrics come only from API data.
- Unknowns: no user-behavior analytics were inspected; layout friction is an evidence-based design judgment, not a measured conversion problem.

## Audit and revision contract
- Viewed live home/catalog through the user's Edge extension. Catalog controls and repeated scope summaries occupy almost the whole first viewport. Home's large laboratory promotion precedes the full quote list.
- Local home promotion references undeclared `--foreground`, `--card`, `--hover` tokens. Reuse existing tokens rather than add aliases.
- Preserve: approved paper/ink/signal palette, Geist typography, brand assets, URLs and working business behavior.
- Remove: duplicate scope explanation, oversized promotion footprint and undefined token references in the affected home section.
- Strengthen: price alignment, compact filter orientation, honest labels, mobile touch targets and clear expansion/recovery.
- Locked: pricing calculation, grouping, ordering, pagination, APIs, SEO routes, source/risk evidence.

## Visual calibration
- Personally viewed `signal-ledger-r2.png` and `pilot-catalog-desktop.png`. Existing control record decomposes the adjacent human-made data-directory family (OpenRouter, Vercel AI Gateway, Cloudflare Radar); reuse established project patterns without new external product research.
- Benchmark reading loop: orientation → search/scope → aligned evidence → next action. Six type roles; strong quiet heading zone followed by denser data rows; no image processing because the product is data-led.
- Current palette/type cause: retain this product's already-approved identity, not a palette from another project. Reject a neon dashboard or decorative display face.
- Target: at least four related design acts per affected state: hierarchy, numeric alignment, semantic color, responsive recomposition and expansion/recovery feedback. Retain readable evidence rather than reduce text to fit.
- Spacing: 4/8/12/16/24/32/48/64. Type roles: display 48–64, page 32–44, section 24–32, body 16, compact 14, label 12; price 20–28 with tabular figures.
- New copy is limited to navigation, labels and truthful descriptions of existing functions; newly phrased descriptions are editorial drafts, not new factual claims or user-approved copy.

## Acceptance
- Typecheck and focused rendering/interaction checks; default and active filtering preserve URL parameters and server behavior.
- No horizontal page overflow at 390px/1440px; mobile controls retain usable targets; reduced motion remains supported.
- Record visual review and actual limitations separately. Production is not changed by this task.
