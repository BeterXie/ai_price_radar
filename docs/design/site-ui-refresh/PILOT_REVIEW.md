# Gate 2 production pilot review

Review status: ready for user approval

## Reviewed renders

- `pilot-home-desktop.png` — 1440×900 production build
- `pilot-home-mobile.png` — 390×844 production build
- `pilot-catalog-desktop.png` — 1440×900 production build
- `pilot-catalog-mobile-filter.png` — 390px mobile expanded-filter state

## Visual review

- Subject specificity: the field reads as a public quote ledger through snapshot time, stock, source, selected scope, and observed-price evidence. Removing the title would still leave a product-specific comparison system.
- Hierarchy: home moves from proposition to search to fresh quotes to live counts; catalog moves from scope selection to selected-condition summary to filter disclosure to grouped quotes.
- Type: desktop home title is 67.68px on one line; mobile title is 43px on two phrase-safe lines. The UI ladder uses display, page, section, body, compact, and label roles. Pilot minimum visible type is 11px; mobile filter labels are at least 12px.
- Color: `#bae64c` is limited to freshness, inventory, selection, and success; `#1f645c` carries information and coverage links. Paper, panel, ink, and neutral lines carry the comparison field.
- Interaction and recovery: home search reaches the catalog and catalog search now filters real groups. The advanced filter state is directly renderable with `?state=filter-open`; apply and reset paths are visible. Missing metadata no longer removes the quote list and receives a factual recovery message.
- Responsive: desktop and mobile pilots have zero horizontal overflow. Mobile navigation, search, rails, selected-condition cells, and filter form recompose instead of shrinking the desktop layout.
- Touch: expanded mobile filter selects and submit button are 44px; price inputs were raised from 42px to 44px.
- Copy: prices use `观测价`; related products use `相关商品另有 … 起`; deliverable copy has no Victor blacklist hits. Search labels, scope summaries, and recovery text describe the actual behavior.
- Technical: TypeScript checking and the Next.js production build pass; all 64 static routes/pages generated successfully. Python API files compile successfully.

## Required views

| View | First attention | Missing proof | Collision | Remaining risk |
| --- | --- | --- | --- | --- |
| Home desktop | Proposition and live quote ledger | None for pilot scope | None | User judgment on overall tone |
| Home mobile | Phrase-safe title and search | None for pilot scope | None | User judgment on mobile density |
| Catalog desktop | Active brand and persistent scope | None for pilot scope | None | Remaining route families not yet translated |
| Catalog mobile filter | Filter task and apply/reset paths | None for pilot scope | None | User approval required before batch implementation |

## Benchmark comparison

Reference family: OpenRouter Models, Vercel AI Gateway Models, Cloudflare Radar, and the current AI Price Radar product identity.

| Measure | Adjacent benchmark pattern | Signal Ledger pilot |
| --- | --- | --- |
| Type levels | Large orientation, page title, section title, readable body, compact row text, labels | Six stable roles with a 67.68px desktop display and 43px mobile display |
| Text anchor regions | Orientation, task controls, current scope, evidence list, status/recovery | Home has proposition, search, quick paths, live ledger, and snapshot rail; catalog has heading, rails, selected scope, stats, filter, and quotes |
| Main-image operations | Not applicable to these image-free operational surfaces | No hero imagery; density comes from data, state, alignment, and interaction care |
| Craft family | Strong separation between macro quiet zones and dense comparison data | Named `Signal Ledger`: paper field, ledger lines, one green state signal, teal information layer, aligned evidence rows |
| Dense / quiet zones | Calm task orientation followed by information-dense data | Home hero supplies quiet orientation before fresh quotes; catalog compresses scope and stats before grouped quote rows |
| Concrete design acts | Functional hierarchy, filter state, evidence grouping, feedback and recovery | Live snapshot rail; semantic search; recent quote ledger; persistent condition summary; responsive filter disclosure; grouped evidence table; graceful metadata recovery |

The pilots reach comparable functional and relational density without inheriting the references' purple, black-and-white, or orange brand surfaces. No unresolved P0 or P1 issue remains. Gate 2 still requires explicit user approval before the remaining route families are produced.
