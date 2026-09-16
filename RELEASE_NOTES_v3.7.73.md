# Release Notes - v3.7.73

## 变更摘要

1. **登录弹窗视口居中修复**:
   - 使用 React `createPortal` 将 `LoginModal` 挂载至 `document.body`，摆脱 `.app-header` 的 `backdrop-filter: blur(12px)` 创建的包含块限制，确保登录弹窗在全屏幕视口正中心垂直水平居中。
2. **QQ 快捷登录收敛**:
   - 在管理员正式配置 QQ 开放平台 App ID 之前，暂时隐藏登录窗口中的 QQ 快捷登录按钮，收敛至邮箱动态验证码免密登录；
   - 未配置时后端 `/api/v1/auth/qq/login` 明确返回 400 Bad Request 提示。
