# Release Notes - v3.7.60

## Summary

Release `v3.7.60` improves the presentation layout of the Pelican bicycle SVG animation benchmark arena:

1. **Pelican Benchmark 2-Column Gallery Grid Layout**:
   - In `apps/web/components/skills/pelican-arena.tsx`, upgraded the model showcase into a responsive 2-column gallery grid (`grid grid-cols-1 sm:grid-cols-2`) matching the reference design.
   - Each model card highlights:
     - Header row with bold model name on the left and status badge on the right.
     - Signature color-coded accent divider bar beneath the title.
     - Live SVG 2D animation interactive viewport (16:10 aspect ratio).
     - Model diagnosis verdict pill, file size, line count, and evaluation summary.
     - Direct actions for "大屏深度视窗" and "新窗口全屏".
   - Added view mode toggle between default "双列画廊" (2-column gallery) and "单视窗精选" (focused single viewport with model tabs).
   - All diagnostic evaluations, model names, prompt text, and metric copy are strictly preserved.
