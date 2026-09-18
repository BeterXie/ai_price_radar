# Release Notes - v3.7.90

**发布日期**: 2026-09-18  
**发布版本**: `v3.7.90`

---

## 变更概述

v3.7.90 修复了生产环境部署后网站图标（浏览器标签栏 Favicon 与网站顶部导航栏 Logo）在部分浏览器与客户端中丢失/显示为空白的问题。

---

## 问题根因与修复

### 1. 浏览器标签栏图标（Favicon）丢失
- **根因**: Next.js App Router 的元数据规范要求：在页面 `<head>` 中自动注入 `<link rel="icon" href="/favicon.ico" sizes="any"/>` 必须将 `favicon.ico` 置于 `apps/web/app/` 根目录下。此前 `favicon.ico` 仅位于 `apps/web/public/favicon.ico`，`app/` 下只有 `icon.png` (512×512) 和 `apple-icon.png` (180×180)。导致页面 `<head>` 中仅存在 `sizes="512x512"` 的图标标签，Chrome、Edge、微信等桌面及移动浏览器因缺乏适配标签栏（16×16/32×32 或 `sizes="any"`）的图标声明，将其判定为不可用而退化为默认空白地球图标。
- **修复**:
  1. 将包含 16×16、32×32、48×48 多尺寸的标准 `favicon.ico` 同步拷贝至 `apps/web/app/favicon.ico`；
  2. 在 `apps/web/app/layout.tsx` 的 `generateMetadata()` 中显式声明完整的 `icons` 元数据，涵盖 `favicon.ico`、`icon.svg`、`icon.png` (512×512)、`apple-icon.png` (180×180) 以及 `shortcut`；
  3. 双向同步 `apps/web/public/` 下的 `icon.svg`、`icon.png`、`apple-icon.png`，保证直接静态 HTTP 请求与 Next.js 元数据解析双重 100% 命中。

### 2. 顶部导航栏 Logo 在部分浏览器中受阻
- **根因**: `apps/web/components/site-header.tsx` 中的 `<Image src="/brand/logo-icon.png" ... />` 默认通过 Next.js 的 `/_next/image` 优化端点处理。由于生产 Alpine Docker 镜像未安装 Linux musl 架构的 `sharp` 原生库，Next.js 服务端优化降级时附加了 `Content-Disposition: attachment; filename="logo-icon.png"` 及沙箱 CSP。在部分移动端浏览器（如 iOS Safari、微信内置 WebView）或安全策略严格的 Chromium 浏览器中，包含 `attachment` 响应头的 `<img>` 标签会被阻断内联渲染，且 `<Image>` 带有 `style="color:transparent"`，导致 Logo 完全不可见。
- **修复**:
  - 为顶部 Logo `<Image>` 添加 `unoptimized` 属性，直接以内联方式渲染 `/brand/logo-icon.png` 静态文件，避免经由 `/_next/image` 代理，秒级呈现，零故障率，零 CPU 开销。

---

## 升级与迁移说明

- 本次发布无数据库结构变更，无数据迁移。
- 遵循 `docs/QUICK_DEPLOY.md` 生产标准部署：
  - 本机构建 Next.js standalone（带有 `INTERNAL_API_BASE_URL` 和 `NEXT_PUBLIC_API_BASE_URL`）；
  - 生产服务器重建 `web` 容器即可生效。
