# Release Notes - v3.7.62

## Summary

Release `v3.7.62` updates the site header logo, brand name, and browser tab icon (favicon):

1. **Website Header Brand Icon & Typography**:
   - Replaced the top-left site header icon with the new cyan circular radar price-tag emblem (`/brand/logo-icon.png`).
   - Changed the site brand title text from `AI Price Radar` to `AI Price Memory` (with `公开报价记录` subtitle).
   - Configured crisp retina rendering (`h-9 w-9 object-contain`) and hover scaling transition.

2. **Browser Tab Icon (Favicon) Across All Formats**:
   - Replaced browser tab icons with the centered cyan radar price-tag icon:
     - `apps/web/app/icon.png` (512x512 Next.js App Router metadata icon)
     - `apps/web/app/apple-icon.png` (180x180 Apple touch icon)
     - `apps/web/app/icon.svg` & `apps/web/public/icon.svg` (SVG wrapper with embedded high-res icon)
     - `apps/web/public/favicon.ico` (multi-resolution 16x16, 32x32, 48x48)
     - `apps/web/public/icon.png` (direct static fallback)
