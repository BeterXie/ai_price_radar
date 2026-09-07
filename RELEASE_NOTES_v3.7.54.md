# Release Notes v3.7.54

## 变更摘要

- **动画沙箱视窗彻底修复（`DemoIframe` & `srcDoc`）**：
  - 针对 Chromium / Edge 浏览器在内嵌 iframe 时受安全头冲突（`X-Frame-Options` / 304 缓存拒绝）导致出现禁止加载图标的问题，重构为 `DemoIframe` 组件。
  - 通过前端直接异步获取完整单文件 HTML 内容，并通过 `srcDoc` 结合 `sandbox="allow-scripts"` 内存注入渲染。完全免去二次网络请求与安全头拦截，确保 2D SVG 机械动效毫秒级流畅播放。
  - Caddy 反向代理补充 `@demos path /demos/*` 专用规则，移除 `X-Frame-Options` 并启用 `Content-Security-Policy: frame-ancestors 'self'`。
- **举例模型全面升级为前沿主力模型**：
  - 将所有技能与降智评测的 `target_models` 从旧版（如 `Claude 3.5`, `GPT-4o`）统一升级为当前前沿主力模型：
    - `GPT-6 Astra` / `GPT-5.6`
    - `Claude 4.5 Sonnet`
    - `Gemini 3.8`
    - `Codex++` / `o3` / `o1`
  - 启动预置脚本（`seed_default_community_skills`）支持对已存在的技能自动同步最新模型标签与正文。
- **贴心低扰动新功能弹窗通知（`NewFeatureModal`）**：
  - 新增全局新功能提示组件：仅在首次访问且整站浏览满 30 秒后才温和弹出，绝不干扰用户即时查价。
  - 用户若已处于 `/skills` 或 `/admin` 页面则自动静默不弹。
  - 一旦点击「稍后再看」或「立即试玩竞技场」即永久静默（写入 localStorage），绝不重复弹窗打扰。

## 验证

- 后端 332 项测试全部通过。
- 前端生产构建成功，65 个路由页面编译无误，无 localhost API 泄露。
