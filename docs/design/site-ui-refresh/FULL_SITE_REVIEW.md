# Signal Ledger full-site review

Review status: production implementation complete

## Delivered route families

- Home, catalog, product detail and source detail
- Guide index, brand/product/delivery/workflow guides and long-form articles
- Watchlist and Atom subscription
- Source submission and local JSON conversion tool
- About, methodology, corrections, developer, privacy, terms and security pages
- Admin access gate, queues, source discovery and offer review

## Independent state routes

| Surface | State URLs |
| --- | --- |
| Catalog | `?state=filter-open`, `?state=meta-error`, `?state=catalog-error`, `?state=report-success`, `?state=report-error` |
| Product | `?state=history-empty`, `?state=report-success`, `?state=report-error` |
| Watchlist | `?state=empty`, `?state=loading`, `?state=error` |
| Source submission | `?state=success`, `?state=error` |
| JSON converter | `?state=error` |
| Admin | `?state=error` plus the default locked state |

## Representative renders

- `full-product-detail-desktop.png`
- `full-guides-desktop.png`
- `full-methodology-desktop.png`
- `full-watchlist-empty-mobile.png`
- `full-shop-submit-success-mobile.png`
- `full-guide-article-mobile.png`
- `full-admin-error-desktop.png`

## Visual and interaction review

- Product detail: 1440×900, 46.08px page title, 11px minimum visible type, zero horizontal overflow. The first viewport contains active scope, evidence counts, observed-price ledger, watch action and official reference.
- Guide index: 1440×900, single-line title, searchable filters in the first viewport, three-column evidence cards and zero horizontal overflow.
- Methodology: 1440×900, eight factual ledger rows with a 328px / 964px title-to-explanation relation and zero horizontal overflow.
- Watchlist empty: 390×844, one clear recovery action at 44px and zero horizontal overflow.
- Source submission success: 390×844, mobile order is title → result → eligibility; both next actions are 44px and the result fits in the first viewport.
- Guide article: 390×844, phrase-safe two-line title, five 44px mobile TOC targets, article evidence visible in the first viewport and zero horizontal overflow.
- Admin error: 1440×900, explicit retained-input recovery copy, disabled dependent action, 44px access controls and zero horizontal overflow.
- Copy: all display pricing language uses `观测价`; related products are explicitly separated. The Victor copy blacklist has no deliverable-source hits.
- Color: green is reserved for freshness, inventory, selected conditions and success. Teal marks information, coverage and official/reference evidence. Warning and danger surfaces use their semantic tokens.
- Recovery: failed metadata keeps the quote list; catalog load failure preserves scope; form and tool errors retain input; empty/loading/error states provide a next action.

## Benchmark comparison

Reference family: OpenRouter Models, Vercel AI Gateway Models, Cloudflare Radar and the approved Signal Ledger pilot.

| Measure | Benchmark pattern | Full-site result |
| --- | --- | --- |
| Type levels | Six clear roles from orientation to compact labels | Display, page, section, body, compact and label roles remain stable across every family |
| Reading loop | Task → scope → evidence → decision → recovery | Shared page orientation, persistent scope, factual ledgers, grouped evidence, direct next actions and explicit recovery |
| Dense / quiet zones | Calm entrance followed by operational density | Home and guide heroes establish orientation; catalog, detail and admin compress evidence only where comparison requires it |
| State depth | Default, information-dense, empty/error and post-decision | Direct state routes cover filter, recovery, history-empty, watchlist, submission, converter and admin states |
| Craft family | Strong brand system without decorative technical costume | Paper field, ink hierarchy, ledger boundaries, one signal green and one information teal across shared and route-specific components |
| Concrete design acts | At least four related acts per key surface | Responsive recomposition, evidence choreography, semantic color, touch sizing, state feedback, recovery copy and task-specific closing paths |

The full-site implementation reaches the approved pilot's functional and relational density. No unresolved P0 or P1 issue remains.
