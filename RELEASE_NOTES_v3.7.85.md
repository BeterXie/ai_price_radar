# Release Notes - v3.7.85

**发布日期**: 2026-09-17  
**发布版本**: `v3.7.85`

---

## 版本核心亮点

v3.7.85 带来了三大全新功能升级：

### 1. 用户管理与活跃度监控大盘
- **全站用户大盘**：后台控制面板上线「用户管理」独立模块，直观呈现全站注册用户量、7日活跃、今日活跃、当前实时在线（15分钟心跳检测）、按钮总点击数与名下优惠券总数。
- **用户行为与资产洞察**：
  - 会话时长：精确统计单次会话登录时长与全站累计在线时长；
  - 登录 IP 记录：自动记录最新登录 IP 与客户端环境；
  - 按钮点击分析：追踪外链购买直达、领券等按键点击行为与流水；
  - 名下优惠券卡包：直观查看每位用户持有的具体优惠券资产、状态（可用/已核销）与到期时间；
  - 机器人绑定状态：用户列表与画像弹窗清晰展示 QQ 机器人绑定状态、Target ID 及价格通知偏好设置；
  - 账号启停管控：支持管理员一键封禁与解封违规账号。

### 2. 新增 Cursor 与 智谱 AI 品牌
- **前台专区与产品收录**：
  - 网站前台导航与筛选全面接入 `Cursor` 与 `智谱` 两大品牌；
  - **Cursor**: `cursor-pro` (Cursor Pro)、`cursor-business` (Cursor Business)、`cursor-account` (Cursor 账号)；
  - **智谱**: `zhipu-qingyan-vip` (清言会员)、`zhipu-api-credit` (GLM API)、`zhipu-account` (智谱账号)；
  - 配套上线品牌专属图标（Cursor 与 Brain 图标）。
- **智能分类器与种子数据**：
  - 扩展关键词库，智能识别并映射 Cursor 与“智谱 / 智普 / GLM / 清言”相关商品标题。

### 3. 后台主动推送通知系统
- **主动广播弹窗**：管理员可在用户大盘顶部一键发起全网广播。
- **触达受众预览**：动态统计全站绑定邮箱用户数、绑定机器人用户数及去重总覆盖人数。
- **双渠道推送**：
  - 电子邮件：排入系统邮件出件箱队列（`NotificationOutbox`）；
  - 机器人私信：直连 QQ 机器人（`QQBotClient`）向激活绑定的用户即时推送精简通知卡片。
- **推送历史记录**：完整持久化每次广播的标题、正文、渠道、触达量及发送时间。

---

## 升级与迁移说明
- 数据表结构升级：新增 `admin_broadcasts` 表；`users` 表新增 `last_login_at`, `last_login_ip`, `last_active_at`, `total_duration_seconds`, `button_click_count`；`user_sessions` 表新增 `ip_address`, `user_agent`, `last_active_at`。
- 本版本由 `apps/api/app/services/db_migration.py` 在应用启动时自动安全幂等迁移，无需手动停机执行 SQL。
