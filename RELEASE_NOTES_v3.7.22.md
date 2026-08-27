# AI Price Radar v3.7.22 - 16688 Discovery and Classification Coverage

## What changed

- The 16688 discovery adapter now scans the public source marketplace with a bounded global page budget, prioritizing `AI与效率` and then other public categories. It resolves every candidate through the official goods-detail API and deduplicates by canonical shop number.
- 16688-specific classifier aliases now cover the observed `GP.T`/`GTP`/`G Plus`/`G Pro` and `Gro` naming variants, including `G Pro X20`.
- The detector, importer, and administrator reclassification path all use the same 16688 detail fields. Reclassification can restore a high-confidence historical 16688 offer only when it remains active and has no manual hide reason.
- Added public shop and source-platform directory pages plus sitemap entries. A shop appears only when it has a current, visible, approved public offer.

## Safety and data scope

- Discovery does not fabricate a target store count. The current public 16688 source catalog exposes 22 distinct shop numbers; 15 have at least one target AI product under the current classifier.
- Newly discovered 16688 shops still require review by default. `DISCOVERY_16688_AUTO_APPROVE` remains disabled unless explicitly configured.
- No database migration is required.

## Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.22` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.
- Run one complete multi-source refresh, then trigger the authenticated administrator reclassification endpoint before restoring the timers.
