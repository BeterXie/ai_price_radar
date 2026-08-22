# Asset ledger

| Asset | Role | Source / path | Rights / status | Factual status | Crop / composite rule |
| --- | --- | --- | --- | --- | --- |
| AI Price Radar icon | identity | `apps/web/app/icon.svg` | project-owned local asset | factual identity | Preserve geometry; recolor only through existing theme-safe route if needed |
| Platform icons | identity / category | `@icons-pack/react-simple-icons`, `components/platform-icon.tsx` | installed maintained library | factual identity | Keep recognizable brand glyphs; no decorative repetition |
| Product and offer data | evidence | production API and `lib/types.ts` | project data | factual | Never replace with invented demo metrics in production |
| Price history | evidence | `components/price-history.tsx` | project data | factual | Preserve time/value mapping and empty/error truth |
| OpenRouter screenshot | benchmark only | `https://openrouter.ai/models` | external, unknown reuse rights | reference | Do not place or bundle |
| Vercel AI Gateway screenshot | benchmark only | `https://vercel.com/ai-gateway/models` | external, unknown reuse rights | reference | Do not place or bundle |
| Cloudflare Radar screenshot | benchmark only | `https://radar.cloudflare.com/` | external, unknown reuse rights | reference | Do not place or bundle |

Decision trail: local project evidence is sufficient → external sites used only for problem decomposition → no unmet image role → no web asset sourcing → no generation → code-native typography, layout, state and data visualization.
