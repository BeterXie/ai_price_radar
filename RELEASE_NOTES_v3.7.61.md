# Release Notes - v3.7.61

## Summary

Release `v3.7.61` updates the site branding assets and browser tab icon (favicon):

1. **Website Header Brand Logo**:
   - Replaced the top-left navigation icon and text with the newly designed transparent brand logo (`/brand/logo.png`), featuring the concentric radar rings, upward trend arrow, and bilingual typography ("AI Price Radar · AI 订阅比价").
   - Configured crisp retina rendering (`h-10 w-auto object-contain`) and smooth hover opacity transition.
   - Updated JSON-LD structured data organization logo URL to `/brand/logo.png`.

2. **Browser Tab Icon (Favicon) Across All Formats**:
   - Replaced browser tab icons with the glowing neon-blue app-store squircle radar icon with antialiased transparent corners:
     - `apps/web/app/icon.png` (512x512 Next.js App Router metadata icon)
     - `apps/web/app/apple-icon.png` (180x180 Apple touch icon)
     - `apps/web/app/icon.svg` & `apps/web/public/icon.svg` (SVG wrapper embedding high-res raster)
     - `apps/web/public/favicon.ico` (multi-resolution 16x16, 32x32, 48x48)
     - `apps/web/public/icon.png` (direct static fallback)

3. **Social Share Card Consistency**:
   - Updated Open Graph social share templates (`apps/web/app/opengraph-image.tsx` and `apps/web/app/products/[slug]/opengraph-image.tsx`) to match the new vibrant blue/cyan brand identity.
