# AI Price Radar v3.7.39 Release Notes

## Overview

v3.7.39 aligns the admin panel's product category navigation with the frontend catalog hierarchy, introduces a dedicated view for restricted/hidden offers with full moderation actions, and pauses automatic candidate discovery and public submission for Dujiao-Next shops.

## Key Changes

1. **Admin Category Hierarchy Aligned with Frontend**:
   - Replaced the flat product slug list with a two-tier navigation matching the public catalog:
     - **Level 1 (Brand Rail)**: `全部品牌`, `OpenAI`, `Claude`, `Gemini`, `Grok`, `X`.
     - **Level 2 (Product Rail)**: Dynamically displays product category chips matching frontend order under each brand.
   - Grouped reclassification select dropdown (`<optgroup>`) by brand hierarchy.

2. **Dedicated Restricted & Hidden View**:
   - Added dedicated `🚫 受限/已隐藏` and `❓ 未分类商品` navigation tabs with live item count badges.
   - For restricted/hidden offers, displays explicit restriction reasons (e.g. tutorial/non-standard product keywords or admin actions).
   - Provided one-click moderation controls:
     - `恢复公开` (clears restriction reasons and restores visibility) / `隐藏/限制`
     - `批准公开` / `撤回公开`
     - `自动分类` / `目标重分类`

3. **Paused Dujiao-Next Discovery & Submission**:
   - Gated Dujiao-Next discovery in `scripts/refresh_remote.sh` via `ENABLE_DUJIAO_DISCOVERY=false` by default.
   - Removed `dujiao-next` search query from crawler GitHub discovery queries.
   - Disabled the Dujiao-Next option on the public shop submission form (`/shops/submit`) with `(暂停收录)` badge.
   - Filtered out `dujiao_next` from the frontend catalog source platform filters.
   - Documented status in `docs/CONNECTORS.md`.
