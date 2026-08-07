# AI Price Radar · UI Product Design Governance

## Product posture

AI Price Radar is a trust-first comparison utility, not a marketplace and not a generic SaaS dashboard. The redesign keeps dense buying evidence visible while making the interface calmer, easier to scan and more coherent across every route.

## Visual direction

- **Base:** mist white / cool paper background
- **Primary:** violet-indigo for navigation, actions and current state
- **Signal:** electric cyan, used sparingly for trust / live-data emphasis
- **Text:** deep navy rather than pure black
- **Typography:** Geist Sans + Geist Mono for numeric evidence
- **Surfaces:** 18–24px radii, subtle glass treatment and low-contrast shadows
- **Motion:** short tactile state changes only; reduced-motion respected
- **Density:** compact for data tables, more generous for reading and onboarding pages

## Governance rules

1. Price is never shown without surrounding context such as stock, source, fulfillment or observation time where the data model provides it.
2. Primary actions use violet; risk, warning and success states keep their semantic colors and are not repurposed decoratively.
3. Shared navigation, page hero, section intro, form fields, status pills, data surfaces and footer must be reused across route families.
4. Marketing-like gradients are reserved for hero emphasis and primary actions; dense comparison surfaces remain predominantly neutral.
5. Links and controls keep visible focus states, minimum touch targets and reduced-motion support.
6. Policy, methodology and guide pages optimize line length and reading rhythm instead of inheriting data-table density.
7. Admin and conversion tools use the same tokens as public pages so they remain recognizably part of one product.

## Route coverage

The shared design system intentionally covers:

- `/`
- `/products` and `/products/[slug]`
- `/watchlist`
- `/guides` and all guide detail route families
- `/shops/submit` and `/shops/[token]`
- `/methodology`
- `/developers`
- `/corrections`
- `/about`
- `/privacy`
- `/terms`
- `/security`
- `/admin`
- `/tools/json-to-cockpit`
- global not-found, header, footer, community prompts and reusable comparison components
