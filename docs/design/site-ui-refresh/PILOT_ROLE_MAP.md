# Production UI role map

Approved direction: `signal-ledger-r2`

## Route and state families

| Family | Page or state job | Dominant evidence / interaction | Visual carrier | Transition onward |
| --- | --- | --- | --- | --- |
| Home `/` | Explain what can be compared and start a search | Snapshot time, current counts, recently observed in-stock quotes | Large typographic orientation followed by a compact quote ledger | Search or quick scope opens `/products`; quote opens product detail |
| Catalog `/products` | Narrow scope and compare like-for-like offers | Brand/product/source rails, selected filters, grouped offer rows | Dense horizontal ledger with a persistent scope summary | Expand a row, open product detail, or reset filters |
| Product `/products/[slug]` | Verify one product before leaving for a source | Price range, coverage, stock, grouped offers, source text | Product evidence ledger and expandable decision facts | Open source, follow guide, watch, or report |
| Guides `/guides/**` | Explain purchase and recovery tasks | Checklists, steps, source citations, FAQ | Calm long-form reading with semantic callouts | Return to relevant product or continue to next step |
| Watchlist `/watchlist` | Review saved products and recover from empty state | Saved items, threshold, current observed price | Compact personal ledger | Open product, change/remove watch, browse products |
| Submission and tools | Complete input, validation, feedback, and recovery | Form fields, validation result, next action | Calm operational panel with one primary action | Success summary, retry, or return to relevant page |
| Trust and policy pages | State method, limits, rights, and project identity | Factual prose, source boundaries, change records | Restrained readable document field | Continue to data, corrections, repository, or catalog |
| Admin | Operate source and data workflows | Current state, pending work, errors, recovery | Dense operational table using shared tokens | Inspect, retry, accept, decline, or return |

## Gate 2 production pilots

| Pilot | Why selected | Four or more authored acts | Required states |
| --- | --- | --- | --- |
| Home desktop + mobile | Brand entrance and default path | live snapshot rail; approved title scale; semantic search; recent quote ledger; trust mechanism band | fresh data, missing snapshot text, responsive recomposition |
| Catalog desktop | Densest evidence surface | hierarchy between scope and data; semantic rails; selected-condition summary; grouped ledger alignment; expandable evidence | default, filtered, empty/recovery |
| Catalog mobile filter disclosure | Most unusual interaction state | stacked scope order; 44px controls; visible selected count; contained filter disclosure; clear apply/reset paths | closed, open, empty result |

## Pilot approval boundary

The production pilots were approved on 2026-08-22 after the user received the explicit Gate 2 approval request and replied “确认”. The remaining route families were then released for implementation.

## Full-site implementation status

| Family | Status | Delivered state coverage |
| --- | --- | --- |
| Home | complete | live snapshot, recent quotes, responsive search |
| Catalog and product | complete | filtered, filter-open, metadata recovery, catalog error, report success/error, history empty |
| Guides | complete | searchable index, long-form article, mobile and sticky TOC, checklists, comparisons, sources |
| Watchlist | complete | populated, empty, loading, error, Atom copy feedback |
| Submission and tools | complete | form, submitting, success, error, local conversion input/output/error |
| Trust and policy | complete | factual ledger, public corrections empty/error/list, source health |
| Admin | complete | locked, loading, invalid/API error, review queues, accept/decline/retry controls |
