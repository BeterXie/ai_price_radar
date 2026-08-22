# Current-site audit

Audit date: 2026-08-22

## Surfaces inspected
- Desktop: homepage, full catalog, product detail, guide hub, buying-checklist article, empty watchlist, source submission, JSON converter.
- Mobile 390×844: homepage, catalog, guide hub.
- Code: 21 page routes, shared header/footer/shell, catalog workspace, filters, offer table, forms, guide system, prompts and 975-line global stylesheet.

## What already works
- The paper / black ink / fluorescent signal palette is recognizable and appropriate to a live price record.
- Public facts, update time, source boundaries and non-transaction disclaimer are visible.
- Desktop catalog supports detailed filtering without horizontal overflow.
- Mobile routes recompose instead of shrinking the desktop canvas; catalog filters already use disclosure.
- Guide articles have a readable measure, sticky table of contents and factual source layer.
- Forms preserve input and expose success/error/limited states.

## Priority issues

### P1 — system coherence
- `globals.css` contains three complete token and component generations (`:root` at lines 3, 363 and 707). The rendered result depends on cascade history rather than one intentional system.
- Repeated selectors for header, hero, surfaces, buttons and fields make future visual changes risky and route-specific exceptions hard to reason about.
- Route families use different density conventions: the homepage is editorial, the catalog is a long ledger, tools use numbered technical panels, policy pages are sparse prose, and empty states carry too little useful onward guidance.

### P1 — comparison efficiency
- Desktop catalog puts three horizontal filter rails, four statistics, a large filter form and a long offer list in one vertical stream. Current state is visible, but the user repeatedly travels between filters and results.
- Offer rows prioritize raw merchant titles; decision facts are visually secondary, creating fatigue in a 1,600+ group list.
- There is no explicit list/compact-table choice for different comparison styles.

### P1 — mobile compression
- Homepage search placeholder is visibly truncated at 390 px because the submit button reserves too much width.
- Mobile catalog requires several swipes through brand/product/source rails before reaching state and results.
- Guide search exposes four stacked fields before the first content section; useful, but heavy for a small screen.

### P2 — state and recovery care
- Empty watchlist leaves a large quiet region with one CTA; it should teach what can be followed and show the next two useful routes without inventing content.
- Loading and skeleton behavior is inconsistent across route families; long-running operations need one shared status language.
- Community prompts, support dialog, submission feedback and converter feedback use their own surface treatments rather than one dialog/toast/state family.

### P2 — copy and rhythm
- Several pages repeat similar caveats in hero, section and footer. The facts are necessary, but their placement can be consolidated into a persistent “data boundary” component.
- Some interface labels are implementation-led (“比较范围”“来源平台”) without immediately stating their effect on results.
- Tool microcopy such as “01 / 输入” and “02 / 输出” reads as technical furniture rather than task guidance.
- Blacklist hits in guide and policy content are mostly factual distinctions and must be source-justified in `PROCESS.md`; promotional contrast templates should still be removed where they appear.

## Direction recommendation
`signal-ledger` is the recommended base. It preserves the product’s strongest existing identity, solves the current hierarchy and state problems, and avoids turning a public comparison service into either a dark operator console or an editorial publication. Useful parts of the other directions can enter only as functional variants: the Workbench’s desktop filter workspace and the Atlas’s guide index rhythm.
