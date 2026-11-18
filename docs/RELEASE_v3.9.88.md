# v3.9.88

Price-drop and Team low-price reports now link to `/offers/{offer_id}` on PriceMemo instead of sending visitors straight to the merchant. Each link identifies the exact merchant SKU, including when multiple listings share the same title.

The new page reuses the existing quote-details presentation and displays the current price, stock, seller, original description and merchant purchase link. Reads bypass frontend caching and use the current public snapshot; hidden, expired, removed or unapproved listings return an explicit unavailable page instead of another offer. The page is noindex and works on desktop and mobile. Existing modal quote details remain available.

Validation covers exact SKU identity, refreshed price and stock, visibility restrictions, site URLs in notifications, server-rendered detail content, unavailable links and temporary API failures. Desktop and mobile views were checked through the Edge browser extension.

No database migration or pipeline changes. Follow QUICK_DEPLOY.md and MULTI_BRAND_DEPLOY.md for API, importer and the five frontend builds. This ordinary API/Web release does not require another full crawler refresh.
