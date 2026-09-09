# Release Notes v3.7.63 - 统一网站主图标与标签栏图标

**Release Date:** 2026-09-10  
**Version:** 3.7.63  

---

## 变更概要 (Overview)

根据用户需求，将网站左上角主图标（Header Logo Icon）与浏览器标签栏图标（Tab Favicon）统一替换为最新设计的高质感松石绿（Teal）雷达 "P" 字圆角徽标。

---

## 主要更新点 (Key Updates)

1. **网站主图标 (Header Logo)**
   - 替换 `/brand/logo-icon.png` 与 `/brand/logo.png` 为新版松石绿雷达 "P" 徽标，尺寸统一规范为 512×512 高清 PNG。
   - 保留网站左上角标题 `AI Price Memory` 与副标题 `公开报价记录`。

2. **浏览器标签栏图标 (Tab Bar Favicon)**
   - 全格式统一覆盖：
     - `apps/web/app/icon.png` (512×512)
     - `apps/web/public/icon.png` (512×512)
     - `apps/web/app/apple-icon.png` (180×180 Apple Touch Icon)
     - `apps/web/public/favicon.ico` (多尺寸嵌入 16×16, 32×32, 48×48)
     - `apps/web/app/icon.svg` & `apps/web/public/icon.svg` (SVG 包装)

3. **Open Graph 社交预览图色彩协同**
   - 更新 `apps/web/app/opengraph-image.tsx` 和 `apps/web/app/products/[slug]/opengraph-image.tsx`，将主视觉点缀色调整为匹配徽标的品牌青绿色（`#00bba9`），标题统一为 `AI Price Memory`。
