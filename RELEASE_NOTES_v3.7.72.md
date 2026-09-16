# AI Price Radar v3.7.72 — Telegram/QQ Bot Infrastructure, User Auth & Dynamic Bot Controls

## 概述
本版本引入了多通道通知与用户中心体系，支持 Telegram/QQ 机器人价格变动私聊推送、邮箱验证码登录、QQ 快捷登录、手机 QQ 扫码一键绑定机器人、交互查价指令（plus/pro/行情/降价），以及后台全局动态启停控制。私有机器人代码严格物理隔离，不影响开源仓库独立发布。

## 核心改进

1. **机器人通知基础设施与安全解耦（`apps/api/app/services/notification_hub.py`）**：
   - 抽象通用变动事件模型 `PriceChangeEvent` 与安全派发门面 `dispatch_price_changes`、指令路由 `handle_inbound_chat_message`。
   - 动态加载本地私有扩展模块，开源环境或未安装扩展时自动平滑降级，零报错运行。
   - 私有机器人代码保存在 `extensions/` 专属目录并通过 `.gitignore` 排除，彻底杜绝代码外泄。

2. **用户体系与登录认证（`apps/api/app/routers/auth.py`, `apps/api/app/routers/user.py`）**：
   - 新增用户模型（`User`、`UserSession`、`AuthCode`、`UserBotBinding`）。
   - 提供 6 位邮箱验证码安全登录与防刷流控，支持 QQ 互联 OAuth 快捷登录。
   - 个人中心路由（`/account`）支持查看个人资料、关注清单及机器人绑定状态。

3. **手机 QQ 扫码绑定与交互指令（`extensions/bots/chat_commands.py`, `apps/web/components/account-client.tsx`）**：
   - 前端集成二维码原生渲染与 2 秒轮询心跳检测，支持一键绑定与扫码绑定。
   - 核心指令：`plus`、`pro`、`gemini`、`grok`、`查 <关键词>`，严格执行 `is_comparable == True` 且 `stock_count > 1` 门槛。
   - 扩展指令：`行情`（全网底价汇总）、`降价`（历史波动精选）、`我的`、快捷启停开关（`暂停推送`/`恢复推送`/`开启降价`）以及 `/bind <code>`。

4. **后台管理全局动态总开关（`apps/api/app/routers/admin.py`, `apps/web/components/admin-panel.tsx`）**：
   - 后台运营与配置标签页新增「QQ 机器人与价格变动通知开关」，持久化保存在 `SystemSetting`，一键即时生效。
   - 关闭后，前台个人中心完全隐藏机器人卡片，接口 403 阻断绑定请求，指令返回维护提示，后台爬虫变动推送自动静默。

5. **数据库迁移与测试覆盖**：
   - 新增 `scripts/migrate_user_auth_and_bot_v13.py`，支持幂等创建用户与绑定表结构。
   - 自动化测试全量通过（涵盖指令、库存过滤、偏好更新、后台动态启停等）。
