# Four independent frontends

Design read: a structural overhaul of four AI subscription comparison sites for different browsing habits, using the existing Next.js, Geist and Phosphor stack.

The previous implementation shared the same hero, search, directory, product rows, header and footer. Color, radius and a few grid overrides could not establish independent identities. Existing product data, routes, filters, source attribution, auth, analytics and canonical URLs remain the functional baseline. Articles stay scoped to the visited site. No invented prices, charts, rankings or editorial content.

| Site | Structure and visual language | DESIGN_VARIANCE | MOTION_INTENSITY | VISUAL_DENSITY |
| --- | --- | --- | --- | --- |
| AIPrice | Dark quote terminal; vertical navigation on desktop, compact quote rows, cyan numerals, instrument summary and log-style articles | 6 | 2 | 8 |
| AISI Plus | Publication masthead, serif Chinese headlines, asymmetric editorial spread, spacious numbered quote stories, long-form reading column | 7 | 2 | 3 |
| PriceIn | Orange shopping header with search, category tiles, product and offer cards, price-first details, practical buying articles | 5 | 2 | 5 |
| OpenPrice | White document index, utility navigation, numbered sections, explicit columns, monospace metadata, source notes | 3 | 1 | 7 |

Brands own their palette rather than inheriting the operating system color scheme. AIPrice uses a complete dark semantic palette. AISI uses a publication serif because reading is its defining activity; no external font request is needed. Prices retain tabular numerals. Status colors communicate availability and warnings. Hover and focus transitions are brief; no autoplay or decorative motion.

Reusable units are data fetching, authentication, search, filters, offer expansion, source links, article bodies and monitoring controls. Homepage composition, navigation, catalog framing, quote summaries, product overviews and editorial frames belong to each brand. Primary PriceMemo remains on its established layout.

Validation: existing web tests, TypeScript and production builds; desktop and mobile review of home, catalog, product, relay and article surfaces; search, filters, offer expansion, keyboard focus and login entry. Empty directories stay honest. Reading layouts may use local fixtures when no published article exists; fixtures must not enter production content.
