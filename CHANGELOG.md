# Changelog

All notable changes to AI Price Radar are documented in this file.

## [3.7.90] - 2026-09-18

### Fixed
- **网站图标（标签栏 Favicon 与顶部导航栏 Logo）在生产环境展示异常**:
  - **标签栏 Favicon 全尺寸补齐**: 将标准多尺寸 `favicon.ico` 同步放置到 `apps/web/app/favicon.ico` 与 `apps/web/public/favicon.ico`，并在 `layout.tsx` 的 `generateMetadata()` 中显式配置 `icons` 元数据（含 `/favicon.ico`、`/icon.svg`、`/icon.png` 512×512、`/apple-icon.png` 180×180 和 `shortcut`），彻底解决因仅声明 512×512 尺寸导致 Chrome、Edge、微信等浏览器标签栏退化为空白图标的问题；
  - **静态资源双向镜像**: 同步补齐 `public/` 目录下的 `icon.svg`、`icon.png`、`apple-icon.png`，确保客户端无论走 App Router 元数据解析还是直接 HTTP 请求根路径静态图标均 100% 命中；
  - **顶部 Logo 避免代理阻断**: 为 `site-header.tsx` 中的 `<Image src="/brand/logo-icon.png" ... />` 增加 `unoptimized` 属性，直接以内联方式渲染静态图片，避开 Alpine Docker 容器因缺少原生 `sharp` 模块而在 `/_next/image` 中返回 `Content-Disposition: attachment` 与沙箱 CSP 导致的部分浏览器（如移动端 WebView、Safari）拒绝渲染的问题。

## [3.7.89] - 2026-09-18

### Fixed
- **公开快照导出在生产环境失效**: 发布流程通过 `scripts/refresh_remote.sh` 以只读方式挂载仓库（`-v "$ROOT:/workspace:ro"`），而 `publish_catalog.py` 会把快照 JSON 写入 `apps/web/public/data`，因此导出必然抛出 `[Errno 30] Read-only file system`。现在该目录以可写方式单独挂载，并通过 `PUBLIC_DATA_DIR` 显式指向导出路径（更具体的挂载覆盖只读父目录）。
- **Web 容器读取实时快照**: `web` 服务挂载 `apps/web/public/data`，不再只提供构建时烘焙进镜像的副本，`/data/latest.json` 与 `/data/v1/snapshots/<id>.json` 会跟随每次发布更新。

## [3.7.88] - 2026-09-18

### Security
- **封堵 QQ 模拟登录后门**: `mock=true` 与 `/qq/scan-mock` 改由 `QQ_MOCK_AUTH_ENABLED` 显式开关控制（默认关闭）；`QQ_AUTH_ENABLED=false` 时回调拒绝认证，不再静默创建真实会话；
- **OAuth state 校验**: 登录入口将随机 state 绑定到 HttpOnly Cookie（10 分钟），回调在交换授权码前做常数时间比对，防止授权码被植入他人账号；
- **绑定接口越权修复**: 手动绑定校验会话归属当前用户并拒绝已被他人绑定的 target；`/notifications/bot/command` 改为 `require_current_user` 且忽略请求体 `sender_id`；绑定码一次性消费，解绑时撤销待绑定授权；
- **验证码防爆破**: `auth_codes` 新增 `attempts`（连续 5 次失败失效）+ 验证接口 IP 滑动窗口限流 + 原子消费验证码；
- **凭据治理**: 移除源码中硬编码的 LDXP 商户 token（`admin.py`、`sync_ldxp_coupons.py`），改为 `LDXP_MERCHANT_TOKEN` 环境变量注入，缺失时明确失败；同步接口 token 由 Query 改为请求体；
- **日志脱敏**: 生产日志不再记录登录验证码，明文打印需显式开启 `DEV_PRINT_AUTH_CODES`；
- **机器人凭据权限**: `qq_bot_login.mjs` 以 0600 写凭据文件、0700 限制状态目录。

### Fixed
- **优惠券并发竞态**: 活动兑换先锁活动行再校验额度，`claimed_count` 改为原子条件 UPDATE；直兑券改为条件更新；幸运掉券增加用户级锁与进程内互斥，24 小时限领与每日额度不可再被并发绕过；
- **点击计数与防抖**: 报价点击改为 SQL 原子自增，防抖检查与写入置于同一临界区；
- **在线时长记账统一**: 新增 `settle_session_activity`，心跳 / 点击 / 退出共用同一基线结算增量，修复时长重复累加与活跃用户少计；
- **启动迁移补列**: 幂等补齐 `offers.click_count` 与 `auth_codes.attempts`；
- **快照导出对齐公开目录**: 沿用可见性过滤（禁用来源、隐藏报价、过期报价）、可信价 1 元下限、仅 CNY 参与人民币指标、`top_5_offers` 与汇总共用可信集合；
- **快照不可变**: 已存在的快照文件不再覆盖，仅当前已发布快照更新 `latest.json`（历史归档需 `--allow-historical`）；
- **公开数据端点可用性**: 新增 `PUBLIC_DATA_DIR` 并在 compose 共享 `apps/web/public/data` 卷，修复容器内 `/data/*` 必然 404；
- **Next.js API 代理**: 统一 `INTERNAL_API_BASE_URL`（默认 `http://api:8000`）并在构建阶段传入，修正 rewrites 指向 web 容器自身的问题；
- **路由与 Schema**: 删除与 Route Handler 冲突的 `public/` 副本；Schema 用 `oneOf` 区分快照与指针；`/data/*` 补齐 ETag / If-None-Match 与 304 转发；修复 `/data/v1/snapshots/<id>.json` 被清洗成 `<id>json`；
- **机器人网关**: 同步 IO 全部经 `asyncio.to_thread` 卸载；心跳增加 ACK 跟踪与接收超时，半开连接可检测重连；凭据变更重建任务；
- **投递语义**: 广播 / 通用推送仅统计确认送达；Connector 扫码用户不再被跳过；涨价事件不再渲染降价文案；涨跌开关按事件过滤；去重键改为价格变动标识；
- **消息健壮性**: Telegram HTML 字段转义 + 超长报告分批；聊天指令长前缀优先匹配；桥接幂等键合并并发请求、账号重载串行化、IPv6 host 生成合法 URL；
- **关注清单缓存隔离**: 云端缓存按用户 ID 存储、匿名数据独立、迁移失败项保留重试，不再把缓存回写云端；订阅更新合并完整配置，切换渠道不再清空其他设置；
- **管理后台**: 子模块改用已验证密钥挂载并在验证后重新加载；用户搜索改为提交态驱动；用户详情请求按序号防乱序覆盖；券按可使用/已核销/已过期区分；
- **登录体验**: 弹窗补齐焦点管理与 Esc 关闭；发码期间锁定邮箱，验证使用请求时邮箱；导航栏通过 `AUTH_CHANGE_EVENT` 同步所有登录入口；
- **部署脚本**: `migrate_claude_subdivision_v15.py` 的 `--dry-run` 不再写库并尊重人工锁定；v18/v19 迁移正确解析 `sqlite://` URL，且不再把外部店铺活动绑到 pricememo。

### Changed
- 版本号统一为 `3.7.88`（`VERSION`、`app/main.py`、`apps/web/package.json`、版本测试）。

## [3.7.87] - 2026-09-18

### Added
- **机器人核心源码开源 (`extensions/`)**:
  - 正式将 QQ 机器人、Telegram 管理员机器人及扩展组件全量开源至 `extensions/` 目录；
  - 腾讯 QQ 机器人客户端 (`qq_bot.py`)：支持官方 Open API (C2C 与群聊推送) 与 Node 桥接；
  - 腾讯免配置扫码 Connector 协议 (`qq_connector.py`)：支持手机 QQ 扫一扫零门槛快速授权与 AES-256-GCM 解密；
  - 原生 WebSocket 长连接网关 (`qq_gateway.py`)：纯 Python 实现持久化网关监听与实时被动回复；
  - Telegram 管理员报警客户端 (`telegram_bot.py`)：负责系统价格变动推送与管理指令交互；
  - 智能比价指令解析引擎 (`chat_commands.py`)：自然语言比价匹配新增 Cursor 与智谱 (GLM) 全系列；
  - 模块配置与运行说明文档 (`extensions/README.md`)。

### Fixed
- **商品目录空状态体验优化**:
  - 优化品牌筛选在当前快照无在售报价时的展示逻辑：移除冗余的虚线空状态卡片，直接优雅展示「监测商品台账」列表与「提交该品牌店铺报价」快捷通道；
  - `apps/api/app/seed.py` 内置 Cursor Pro、智谱清言会员、智谱 GLM API 与智谱账号基准演示数据。

## [3.7.86] - 2026-09-17

### Fixed
- **数据管道与目录分类器同步 (Cursor & 智谱)**:
  - 在 `pipeline/common.py` 数据处理管道中补充 `cursor` 与 `zhipu` 的 `BRAND_MARKERS`、`classify_identity` 映射以及 `ensure_products` 目录定义，使爬取到的 Cursor 与智谱商品能自动归类到对应的商品台账中；
  - 爬虫调度脚本 `refresh_remote.sh` 补充智谱、清言、GLM 检索关键词；
  - 优化产品列表 API 与前端展示：当品牌分类下暂无现货报价时，前台优雅展示该品牌下纳入监控的各商品卡片，方便用户直接查看商品详情与订阅降价通知。

## [3.7.85] - 2026-09-17

### Added
- **用户管理与活跃度监控大盘**:
  - 后台管理新增「用户管理」独立功能模块，实时追踪全站注册用户、今日活跃、实时在线、总时长、登录 IP 与历史会话；
  - 按钮点击分析：监控全站与单用户的外链购买、领券、订阅等按钮点击数据；
  - 名下优惠券资产洞察：展示用户持有的优惠券总数、可用券、已核销券及详细资产卡包；
  - 机器人绑定状态：列表与画像弹窗清晰呈现 QQ 机器人绑定状态、Target ID 与通知配置。
- **新增 Cursor 与 智谱 AI 品牌专区**:
  - 网站前台导航、分类筛选及产品目录接入 Cursor（Cursor Pro、Cursor Business、Cursor 账号）与 智谱（清言会员、GLM API、智谱账号）；
  - 配套上线分类器智能识别规则与品牌图标。
- **后台主动推送通知系统**:
  - 管理员可自主撰写并向全站用户主动广播系统通知与公告；
  - 覆盖受众预览：实时计算绑定邮箱与绑定机器人的去重触达人数；
  - 双渠道推送：支持邮件队列（`NotificationOutbox`）与 QQ 机器人私信（`QQBotClient`）双发；
  - 历史广播留存：持久化存储推送历史、触达量与发送状态。

## [3.7.84] - 2026-09-17

### Added
- **店铺专属优惠券绑定体系（券跟着店铺走）**:
  - `ShopCoupon` 数据表新增 `shop_id` 外键与索引，`CouponCampaign` 新增 `shop_id`、`shop_url`、`shop_name` 字段与索引；
  - 提供数据库双引擎迁移脚本 `scripts/migrate_coupon_shop_binding_v19.py`，自动回填现有券与活动为对应店铺专属；
  - 后台批量导入券码支持选择已有平台店铺或录入店铺直达链接，自动匹配关联平台店铺并绑定店铺信息；
  - 链动小铺（LDXP）一键同步自动绑定彩头AI官方店铺信息；
  - 营销口令活动（Campaign）强制绑定所属店铺，活动仅发放该特定店铺的立减券；
  - 口令兑换（`/api/v1/user/coupons/redeem`）严格按活动绑定的店铺范围发放券码，杜绝跨店铺滥发或挪用其他商家优惠券；
  - 后台控制面板券码明细支持按“全部店铺 / 具体店铺”快速筛选，口令列表与券码明细增加直观的店铺徽章与直达链接。

## [3.7.83] - 2026-09-17

### Fixed
- **活动口令兑换逻辑与优惠券批次隔离优化**:
  - `ShopCoupon` 数据表新增 `campaign_id` 外键与联合索引，解决活动口令限领配额混淆了幸运掉落与通用券的问题，使每个活动口令的限领配额独立计算；
  - 修复活动口令在指定 `coupon_batch_id` 且对应批次为空时无法分配的问题，增加通用券池自动兜底机制（Fallback），避免因批次配置或误填导致提示“优惠券库存暂时不足”；
  - 后台管理控制面板创建活动口令表单增加友好指引，明确标识批次 ID 为选填（默认 0 通用券池）。

## [3.7.82] - 2026-09-17

### Fixed
- **全部店铺报价列表点击数常态化展示与即时反馈**:
  - 修复全部店铺报价列表（`ShopOfferList`）在点击数为 0 时未展示访问次数的问题，确保每家店铺报价在“查看原站”旁始终直观展示访问量徽章（如 `🔥 0 次访问`、`🔥 1 次访问`）；
  - 前端引入点击即时响应（乐观更新机制），用户点击“查看原站”或单品“去原站查看”时即刻增加点击数并点亮火焰图标，带来即时互动反馈。

## [3.7.81] - 2026-09-17

### Added
- **商品外链点击统计与店铺访问量看板**:
  - `offers` 表新增 `click_count` 字段，提供报价列表与详情卡片 $O(1)$ 极速访问读取；
  - 新增 `offer_clicks` 访问明细表与双引擎幂等迁移脚本 `scripts/migrate_offer_clicks_v17.py`，支持记录访问事件、商户、IP 哈希与客户端环境；
  - 后端提供 `POST /api/v1/offers/{offer_id}/click` 与 `POST /api/v1/shops/{token}/click` 上报接口，内置 60 秒 IP 防重复防刷频控；
  - `GET /api/v1/shops/{token}` 新增返回商家**“当日商品点击数”**（北京时间当天 0 点至今）与**“累计总点击数”**；
  - 前端商品卡片和详情展开表格全面增加访问热度徽章（🔥 次访问），用户点击“查看原站”或“去原站查看”时使用 `keepalive: true` 原生保活异步无感上报；
  - 店铺主页（`/shops/[token]`）全新加入商家访问数据看板与原店铺访问行为追踪组件 `ShopVisitButton`；
  - 新增完备的单元测试 `apps/api/tests/test_offer_clicks.py`，覆盖外链上报、频控防刷、商户主页聚合及各接口反序列化。

## [3.7.80] - 2026-09-17

### Added
- **店铺专属卡包、LDXP 真实优惠券池、动态概率掉落与后台营销中心**:
  - 新增 `shop_coupons`（优惠券池表）与 `coupon_campaigns`（活动营销口令表），支持持久化链动小铺（LDXP）真实 10 位券码（如满 15 减 5 元）；
  - 新增幂等数据库结构迁移脚本 `scripts/migrate_shop_coupons_v16.py`，支持 PostgreSQL 与 SQLite；
  - 新增商户后台同步工具 `scripts/sync_ldxp_coupons.py`，支持自动拉取官方 SalesCoupon 批次与 10 位券码，保持卡券库存充沛；
  - 新增后端用户卡包与动态概率 API：
    - `GET /api/v1/user/coupons/drop-status`：根据当前剩余未领库存动态微调掉落概率（低库存阶梯衰减）；
    - `GET /api/v1/user/coupons`：获取当前登录用户已持有的专属卡券列表；
    - `POST /api/v1/user/coupons/redeem`：支持活动口令（如 `RADAR888`）或直接券码核销兑换；
    - `POST /api/v1/user/coupons/claim-drop`：领取前台幸运彩蛋券，严格校验掉落开关、单人单日配额与剩余库存；
  - 后台管理（`/admin?tab=coupons`）全新上线【优惠券与营销管理】控制面板：
    - 实时监控可用库存、已发放数、已核销数、口令数与掉落状态；
    - 支持在线配置前台随机掉落开关、基准概率滑块、库存紧缺自适应控频与单用户每日领取上限；
    - 集成一键从链动小铺(LDXP)同步券码，以及多行文本批量导入券码并自动排重；
    - 完整的券码明细表格（支持状态筛选、模糊搜索、分页与安全删除）；
    - 营销活动口令（如 `RADAR888`）的生命周期、单人限额与配额进度管理；
  - 前端个人中心（`/account`）新增【🎁 我的专享卡包】卡片：
    - 展示面额（¥5 满15元可用）、专属 10 位券码、一键复制、直达彩头AI店铺下单；
    - 集成口令快速兑换输入框；
  - 前台全局布局挂载【🎁 锦鲤彩蛋随机概率掉落】浮窗（`LuckyCouponDrop`），浏览比价时基于后端动态概率随机触发立减券掉落，引导一键存入卡包并完成“比价 $\to$ 领券 $\to$ 店铺下单”闭环。


## [3.7.79] - 2026-09-17

### Fixed
- **机器人查价与公共前台大盘规则严格对齐与异常过滤**:
  - 彻底解决 QQ / Telegram 机器人查价时可能返回后台已封禁（如管理员限制、自动过滤、未审核）或异常极端低价诱饵报价的问题；
  - 机器人报价查询统一接入前台标准公共查询引擎（`_base_public_offer_query` + `_median_prices` + `_is_trusted_offer`）：
    - 严格只允许 `Offer.active == True`、`Offer.approved == True`、`hidden_reason == ""` 的有效报价；
    - 严格限制店铺 `Shop.is_visible == True` 且平台非禁用状态，且在 `stale_offer_hours` 新鲜度窗口内；
    - 执行中位价异常过滤（`_is_trusted_offer`），自动剔除低于 1 元或低于同交付形态中位数 40% 的异常报价；
    - 优先推荐多库存现货（`stock_count >= 2`），单件微库存兜底；
  - 覆盖品牌全系列聚合（`query_brand_lowest_prices`）、单品深度对比（`query_lowest_price`）、大盘行情（`query_market_overview`）、降价追踪（`query_recent_drops`）与个人订阅盯盘（`query_user_subscriptions`），实现机器人答复与网页前台展示的 100% 精确一致。

## [3.7.78] - 2026-09-17

### Added
- **Claude 细分规格矩阵与精准同质可比体系**:
  - 新增 `claude-pro-20x`（Claude Pro 20x 满血高配号）与 `claude-team`（Claude Team 团队版席位与组织号）商品分类；
  - 将原 `claude-pro` 前台名称更新为 `Claude Pro (5x)`，严格限定为个人标准订阅版（$20/月），彻底解决原本 5x、20x 与车位混杂导致的报价失真问题；
  - 编写并集成幂等数据迁移脚本 `scripts/migrate_claude_subdivision_v15.py`，支持存量 Claude 报价按标题语义重分类；
  - 前端 Catalog 分类标签选项卡与 SEO 元数据同步补全。

### Added
- **品牌全系列最低报价聚合卡片**:
  - 当用户在 QQ / Telegram 机器人中发送品牌词（`Claude`、`OpenAI`、`ChatGPT`、`Gemini`、`Grok` 等）时，自动生成该品牌下所有细分商品（如 Pro 5x、Pro 20x、Team、账号、API 额度）的最低可比较现货（`stock_count > 1`、`is_comparable=True`）聚合卡片；
  - 保留单品型号（如 `plus`、`pro`、`20x`、`team`、`advanced` 等）的 Top 5 现货店铺深度比价路由。

## [3.7.77] - 2026-09-17

### Fixed
- **QQ 机器人常驻 WebSocket Gateway 守护与实时对话能力**:
  - 彻底解决用户向 QQ 机器人发送私聊消息时提示“无法对话，提示服务异常”的问题；
  - 根本原因：腾讯 QQ 开放平台规定机器人必须与官方 WebSocket Gateway (`wss://api.sgroup.qq.com/websocket`) 保持实时长连接与心跳；未建立连接时腾讯服务端判定机器人离线，直接向用户展示“服务异常”；
  - 实现纯 Python 原生 `QQGatewayService` (`extensions/bots/qq_gateway.py`)，接入 `websockets` 协议栈，自动维护已绑定 QQ 机器人的长连接、心跳重连与 IDENTIFY/RESUME 会话状态机；
  - 实时监听 `C2C_MESSAGE_CREATE` 入向私聊消息与 `FRIEND_ADD` 好友添加事件，自动调用 `handle_chat_command` 指令路由并附带 `msg_id` 被动回复至用户 QQ 窗口；
  - 在 FastAPI `lifespan` 生命周期中自动托管网关后台线程，平滑启动与优雅退出。

### Fixed
- **全面接入腾讯官方 QQ Bot Connector 扫码协议**:
  - 严格对齐 `Dota AI Decision Lab` 底层依赖（`@tencent-connect/qqbot-connector` 官方协议）；
  - 彻底修复因错误调用微信 ilinkai 协议导致的“手机 QQ 扫码提示请在微信打开”问题；
  - 采用腾讯官方 QQ 网关（`q.qq.com`）：通过 `https://q.qq.com/lite/create_bind_task` 创建扫码任务，生成原生手机 QQ 授权地址：`https://q.qq.com/qqbot/openclaw/connect.html?task_id=...&source=&_wv=2`；
  - 手机 QQ 扫描后直接调起 QQ 官方机器人授权绑定界面，点击确认即可绑定！
  - 轮询 `https://q.qq.com/lite/poll_bind_result`，采用 AES-256-GCM 算法解密官方凭据，自动提取 `app_id`、`app_secret` 与用户的 `user_openid` 完成账号绑定；
  - 绑定成功后立即通过 QQ 官方 OpenAPI 向用户下发欢迎消息与使用指南。
- **跨项目资产同步与依赖增强**:
  - 将 `Dota AI Decision Lab` 中的完整 Node 桥接组件同步至私有 `extensions/qqbot_bridge/`；
  - API 基础依赖新增 `cryptography>=43.0.0`，原生支持标准 AES-256-GCM 高效加解密。

## [3.7.75] - 2026-09-17

### Added
- **价格订阅与降价通知持久化至云端**:
  - 新增 `user_product_subscriptions` 数据库表（`migrate_user_subscriptions_v14.py`），关注商品由纯浏览器存储升级为云端数据库持久化，实现跨设备多端同步。
  - 用户可在关注清单中实时设定降价目标预期价；价格变动或达标时通过已绑定的有效邮箱与已连接的机器人定向推送。
  - 前端支持未登录用户本地暂存数据在登录后一键自动同步至云端。
- **腾讯 iLink ClawBot 官方免审核协议集成**:
  - 参考 Dota AI Decision Lab 深度集成腾讯官方 iLink 机器人协议（`bot_type=3`）；
  - 零门槛免开发者平台申请审核，接口直接获取官方二维码，手机微信/QQ 扫码后弹窗一键加机器人为好友并建立双向私聊会话。
- **机器人智能指令增强**:
  - `plus`、`pro` 等高频指令优先返回可比且现货库存充足（`stock_count > 1`）的最低现货；
  - 新增 `team`、`api`、`特惠`、`关注`（即时查询本人关注清单最新价与达标情况）等实用指令。
- **关注清单页面重构**:
  - 全新升级 `/watchlist` 页面，遵循 Warm Paper 暖色报纸设计系统，直观展示商品状态、当前可比最低价、目标预期价设定、邮件与机器人渠道独立开关，并保留 Atom/RSS 订阅地址生成。

## [3.7.74] - 2026-09-17

### Fixed
- **彻底去除开发调试按钮**:
  - 移除了个人中心二维码授权区域遗留的 `🧪 模拟手机扫码成功（开发调试）` 按钮，防止线上暴露调试接口。
- **页面设计系统规范统一**:
  - 彻底重构了个人中心（`AccountClient`）与登录弹窗（`LoginModal`）的界面风格，将原先突兀的暗色块替换为 PriceMemo 项目原生温暖报刊纸张设计规范（`var(--panel)`、`var(--paper)`、`var(--ink)`、`var(--line)`、`.surface-panel`、`.button-primary` 等）。
  - 手机 QQ 扫码卡片调整为米白底色配合精细浅灰边框的清爽报刊卡片排版，二维码居中展示并提供优雅状态指示。

## [3.7.73] - 2026-09-17


### Fixed
- **登录弹窗居中与 QQ 登录收敛**:
  - 使用 React `createPortal` 将登录弹窗挂载至 `document.body`，彻底解除 `.app-header` 中 `backdrop-filter: blur(12px)` 对 `position: fixed` 视口定位的干扰，确保登录窗口在全屏正中间垂直水平居中。
  - 在配置 QQ App ID 之前暂时隐藏前台 QQ 快捷登录入口，未配置时后端接口返回 400，引导用户统一使用邮箱验证码安全免密登录。

## [3.7.72] - 2026-09-17


### Added
- **机器人通知基础设施与消息分发解耦**:
  - 新增 `PriceChangeEvent` 变动模型与 `dispatch_price_changes`、`handle_inbound_chat_message` 弱耦合插件化派发门面，动态加载本地私有扩展，无扩展时优雅降级。
  - 私有机器人代码保存在 `extensions/` 专属目录，通过 `.gitignore` 严格隔离，杜绝公开仓库泄漏。
- **用户体系与全链路认证**:
  - 新增 `User`、`UserSession`、`AuthCode`、`UserBotBinding` 模型与 `scripts/migrate_user_auth_and_bot_v13.py` 迁移脚本。
  - 支持邮箱 6 位验证码登录与 QQ 互联快捷登录，新增个人中心路由（`/account`）。
- **手机 QQ 扫码绑定与交互查价指令**:
  - 前端支持手机 QQ 原生扫码授权与一键绑定当前登录 QQ。
  - 机器人交互指令全面支持 `plus`、`pro`、`gemini`、`grok`、`查 <关键词>`，严格要求 `is_comparable == True` 且 `stock_count > 1`。
  - 支持大盘行情（`行情`）、今日降价精选（`降价`）、个人设置（`我的`）、聊天内快捷启停开关（`暂停推送`/`恢复推送`）。
- **管理后台全局动态启停开关**:
  - 后台运营与配置新增「QQ 机器人与价格变动通知开关」，保存在 `SystemSetting` 中即时生效。
  - 关闭后前台个人中心完全隐藏机器人卡片，接口 403 阻断绑定请求，指令返回维护提示，后台爬虫推送静默。

## [3.7.71] - 2026-09-16

### Added
- **后台纠错与风险反馈多状态筛选与归档查看**:
  - 管理后台【纠错与风险反馈】Tab 增加二级状态筛选切换栏（待处理、已处理、已驳回、全部记录），支持红点角标待办提示与一键刷新。
  - 增强已处理与已驳回卡片详情展示，支持查阅用户预留联系方式、历史公开摘要、商家回复与处理时间戳。
- **公开纠错页（`/corrections`）直接提交入口**:
  - 在公开纠错记录页面底部增加 `ReportForm`，方便访客与商户在查看纠错记录时直接提交新的问题反馈。

### Fixed
- **纠错反馈管理 API 支持全量状态检索**:
  - `GET /api/v1/admin/reports` 增加对 `status=all` 的支持，解除此前仅能拉取单状态的限制，保持与前端多状态筛选对齐。
  - 完善后台纠错接口单元测试套件（`test_admin_reports_status_filtering`）。

## [3.7.70] - 2026-09-16

### Fixed
- **商品详情展开“全部店铺报价”空白问题修复**:
  - 修复后台爬虫更新快照后，客户端携带旧 snapshot ID 查询同款商品分组店铺报价返回空列表 `items: []` 的缺陷。在 `_snapshot_for_query` 中增加有效报价检测，对已被接力覆盖的旧快照自动降级至当前最新快照。
  - 在 `get_group_offers` 增加容灾兜底策略，若前台带严格过滤条件或快照不一致导致查询结果为空时，自动回退查询当前快照下的该款式同款店铺，确保同款店铺列表稳定渲染。
  - 前端 `OfferRow` 展开店铺报价时不再携带过期 snapshot 参数，并在接口返回空或异常时自动降级展示代表店铺报价；优化 `ShopOfferList` 边界态，彻底消除空边框容器。

## [3.7.69] - 2026-09-16

### Added
- **后台模块 Tab 化导航**:
  - 管理后台增加顶部吸顶 Tab 导航栏（运营与配置、店铺审核、社区文章、公网来源发现、纠错反馈、报价分类），支持未处理角标 Badge、URL 参数同步以及 0ms 状态保留切换。
- **页面顶部横条公告（Site Notice）动态配置**:
  - 后台支持配置启用/停用开关、徽标（badge）、主标题、正文说明、按钮文案及目标跳转链接，提供前台实时渲染预览卡片与快捷开关，前台刷新实时生效并保留用户本地关闭状态。
- **加入 AI 比价交流群引导（Community Notice）动态配置**:
  - 后台支持配置入群引导弹窗开关、弹窗主标题、详细文案、QQ群号、加群链接及按钮文案，配备实时渲染预览卡片与快捷开关。

### Fixed
- **文章编辑弹窗“保存发布”按钮隐形修复**:
  - 修复全局变量缺失导致编辑弹窗保存按钮透明底白字隐形的问题，在 globals.css 中补充映射并加固按钮样式。
- **加入交流群弹窗加群按钮黑底黑字修复**:
  - 修复 Tailwind CSS v4 下 `a { color: inherit; }` 全局未分层样式覆盖 utility 类导致链接按钮黑底黑字隐形的问题，移入 `@layer base` 并为按钮文字追加 `!text-white`。

## [3.7.68] - 2026-09-15

### Added
- **公共数据快照与开发者文档规范**:
  - 提供不可变快照目录与接口规范文档（`/price-radar-api.md`、`/price-radar-v1.schema.json`、`/.well-known/price-radar.json`）。
  - 开放 `/api/v1/feed` 公共 Feed 路由。
  - 数据管道发布后自动生成最新只读不可变快照（`pipeline/export_snapshot.py`），支持前端直接读取快照渲染。

### Changed & Improved
- **商品类型切换无感过渡 (Smooth Tab Transition)**:
  - 彻底移除 `apps/web/app/products/[slug]/loading.tsx`，避免 Next.js App Router 路由跳转触发全局卸载和骨架屏白屏闪烁。
  - 开启商品类型 Tab 链接预取 (`prefetch={true}`) 与 30 秒客户端路由缓存 (`revalidate = 30`)。
  - 使用 React `cache()` 消除元数据与详情页重复网络开销，实现商品类型即点即换，零白屏无感切换。
- **API 稳定性与网络超时优化**:
  - `apiFetch` 增加超时中断与取消信号，避免并发静态生成或网络波动时请求挂起。

## [3.7.67] - 2026-09-15

### Changed & Improved

- **全站品牌与可见文案统一为 AI Price Memory**:
  - 网页界面直接可见的内容（页脚、关于页、合作推广页、数据来源页、指南免责声明、社区弹窗等）统一替换为 `AI Price Memory`。
  - 涉及 SEO 的元数据（`title`、`description`、`openGraph.siteName`、Schema.org 结构化数据）在保留原有 `AI Price Radar` 权重的同时全面追加融入 `AI Price Memory`。
- **SSR API 请求瞬态抖动重试**:
  - `apps/web/lib/api.ts` 中的 `apiFetch` 增加指数退避重试（针对 Docker 内部 DNS 解析 `api` 出现的 `EAI_AGAIN` 等网络异常自动重试），大幅提升服务端渲染稳定性。


### Fixed

- **收录完成邮件地址与文案**:
  - 修复 16688 单品链接（`/goods/G...`）收录完成后，「本站收录页面」错误套用申请表的 `source_key`，生成 `https://ai.pricememo.cn/shops/https://www.16688.com.cn/goods/G22076118` 这类无效地址的问题；现在只在校验到真实店铺 token 时才输出收录页链接，否则省略该行。
  - 店铺名称为 URL（如 `www.16688.com.cn`）时自动替换为店铺真实名称。

### Changed & Improved

- **「店铺已收录，新增商品无需重新申请」通知**: 当提交地址是已收录店铺的商品页面时，改为发送收录规则说明邮件（新事件 `shop_intake.goods_added`），提示系统会自动扫描同步新增商品、无需重复提交申请；首次收录的新店铺仍发送「店铺已正式收录」。
- `pipeline/backfill_published_intake_emails.py` 支持 `--intake-id` 与 `--replace`，用于针对单条申请补发正确邮件。

## [3.7.63] - 2026-09-10

### Changed & Improved

- **Unified Brand Icon & Tab Bar Favicon**:
  - Replaced the website top-left main icon (`/brand/logo-icon.png`, `/brand/logo.png`) and the browser tab bar favicon across all formats (`app/icon.png`, `app/apple-icon.png`, `app/icon.svg`, `public/favicon.ico`, `public/icon.png`, `public/icon.svg`) with the unified teal radar "P" emblem squircle.
  - Kept the header brand title as `AI Price Memory` with subtitle `公开报价记录`.
  - Harmonized Open Graph preview images in `apps/web/app/opengraph-image.tsx` and `apps/web/app/products/[slug]/opengraph-image.tsx` with the teal brand color scheme (`#00bba9`).

## [3.7.62] - 2026-09-10

### Changed & Improved

- **Header Brand Typography & Icon Update**:
  - Replaced the top-left site header icon with the new cyan price-tag radar emblem (`/brand/logo-icon.png`).
  - Updated the top-left brand title from `AI Price Radar` to `AI Price Memory`.
  - Replaced the browser tab bar icon (favicon) across all formats (`app/icon.png`, `app/apple-icon.png`, `app/icon.svg`, `public/favicon.ico`, `public/icon.png`) with the new centered cyan radar price-tag icon.

## [3.7.61] - 2026-09-09

### Changed & Improved

- **Brand Identity & Tab Icon Refresh**:
  - Replaced the website top-left corner brand mark and title/subtitle with the new high-resolution transparent logo (`/brand/logo.png`), featuring the vibrant cyan/blue radar graphic with upward trend arrow and "AI Price Radar · AI 订阅比价".
  - Replaced the browser tab bar icon (favicon) across all formats (`app/icon.png`, `app/apple-icon.png`, `app/icon.svg`, `public/favicon.ico`, `public/icon.png`) with the new glowing neon-blue app-store squircle radar icon with transparent rounded corners.
  - Updated Open Graph social card accent colors in `apps/web/app/opengraph-image.tsx` and `apps/web/app/products/[slug]/opengraph-image.tsx` to match the new brand blue.
  - Updated organization logo in `apps/web/components/structured-data.tsx` to point to `/brand/logo.png`.

## [3.7.60] - 2026-09-09

### Changed & Improved

- **Pelican Benchmark 2-Column Gallery Grid Layout**:
  - In `apps/web/components/skills/pelican-arena.tsx`, restructured the model arena presentation into a 2-column gallery grid (`grid grid-cols-1 sm:grid-cols-2`) matching modern model evaluation galleries.
  - Each card features a clean card header (bold model name and badge), a color-coded accent divider line reflecting model tier and status (e.g. rose for Astra full-blood, amber for degraded, purple for skill-enhanced, emerald for flash), an interactive SVG 2D animation viewport, verdict pill, file size / line count metrics, and diagnostic summary.
  - Added a responsive view mode switcher allowing users to toggle between the default "双列画廊" (2-column gallery) and "单视窗精选" (focused single viewport with model tabs).
  - Kept all existing benchmark diagnostic copy, prompt citations, and data metrics completely intact.

## [3.7.59] - 2026-09-09

### Changed & Improved

- **16688 Platform Stock Status Optimization for Continuous & Recharge Goods**:
  - In `pipeline/connectors/platform_16688.py`, optimized `_stock` resolution logic. 16688 goods with `stock_available_quantity = -1` (or negative integers) and non-"out" status now accurately resolve to `(None, "in_stock")` instead of `unknown`. This properly recognizes continuous on-demand supply / auto-recharge services (such as 官方秒充, 直充, CDK) as available in-stock products.
  - Resolved public catalog ranking and filtering issues where 16688 recharge offers (e.g. `#13622` and `#13623` in "凌越穹顶源头招代理") were pushed off the first page or hidden under "仅看有货" filters.
  - Added idempotent database migration script `scripts/migrate_16688_stock_status_v12.py` and unit tests to backfill existing 16688 offers from `unknown` to `in_stock`.
  - Added connector unit tests in `pipeline/tests/test_connectors.py` verifying positive, zero, and negative/unlimited stock values.

## [3.7.58] - 2026-09-09

### Changed & Improved

- **Consolidate ChatGPT Pro Categories into Pro 5x and Pro 20x**:
  - In `apps/web/lib/catalog.ts`, removed generic `chatgpt-pro` tab from `PRODUCT_TABS.OpenAI` and positioned `Pro 5x` (`chatgpt-pro-5x`) and `Pro 20x` (`chatgpt-pro-20x`) side-by-side after Plus.
  - In `apps/api/app/services/classifier.py` and `pipeline/common.py`, enhanced `_pro_multiplier` and classifier logic to eliminate generic `chatgpt-pro` returns. All ChatGPT Pro merchandise now classifies into either `chatgpt-pro-5x` (100刀 / 5x / 5倍) or `chatgpt-pro-20x` (200刀 / 20x / 20倍 / generic Pro fallback).
  - Resolved `(?!\d)` regex lookahead issues with composite titles like `20x 200刀` and multi-tier variant selections like `5x/20x ... · 100刀PRO`.
  - In `apps/api/app/seed.py` and `pipeline/common.py`, legacy `chatgpt-pro` is now automatically marked `is_visible = False`.
  - Created migration script `scripts/reclassify_pro_offers.py` to reclassify existing production offers from generic Pro to Pro 5x or Pro 20x and hide `chatgpt-pro`.

## [3.7.57] - 2026-09-08

### Changed & Improved

- **Published Intake Notifications for 16688 & Catalog Sources**:
  - In `pipeline/publish_catalog.py`, added automatic `shop_intake.onboarded` email notification queueing for published intakes with contact emails upon catalog snapshot release, ensuring 16688, WooCommerce, and custom merchant catalog sources receive their official onboarding confirmation email with active shop link and product count.
  - Added `shop_intake.no_products` notification when an intake has 0 imported products.
  - Added `pipeline/backfill_published_intake_emails.py` utility to backfill missing onboarding notifications for active published merchants.
- **Admin Panel Intake Email Transparency**:
  - In `apps/web/components/admin-panel.tsx`, clearly distinguish between merchants with contact emails and crawler-discovered sources (`无联系邮箱（系统爬虫自动发现，不发送邮件通知）`), preventing administrative confusion on notification delivery.
- **Search Engine Verification & Crawling Optimization**:
  - Configured explicit `robots` and `googleBot` directives (`index: true`, `follow: true`, `max-image-preview: large`, `max-snippet: -1`, `max-video-preview: -1`) in `apps/web/app/layout.tsx`.
  - Added optional Bing and Baidu webmaster verification meta tag injection.

## [3.7.55] - 2026-09-08

### Added

- **Codex Experimental Context Management Article** (`/skills/codex-context-management-experimental-mode`):
  - Added verified technical guide on enabling `[features.context_management] experimental_mode = true` in `~/.codex/config.toml`.
  - Detailed comparison between traditional compaction and note-taking + semantic search context management, helping users conserve tokens and prevent model degradation during long sessions.
  - Linked to ChatGPT Plus and Codex product price comparisons.

## [3.7.54] - 2026-09-08

### Changed & Improved

- **Sandboxed Demo Isolation with `srcDoc`**:
  - Refactored `PelicanArena` and `SkillDetailView` to use `DemoIframe` with `srcDoc` content injection and `sandbox="allow-scripts"`, preventing Chromium iframe security header conflicts (`X-Frame-Options` / cache 304 refusal).
  - Caddyfile configured with `@demos` path removing `X-Frame-Options` and setting `Content-Security-Policy: frame-ancestors 'self'`.
- **Frontier Model Standardization**:
  - Replaced outdated model references (`Claude 3.5`, `GPT-4o`) across skill tags, target models, and benchmarks with contemporary cutting-edge models (`GPT-6 Astra`, `GPT-5.6`, `Claude 4.5 Sonnet`, `Gemini 3.8`, `Codex++`, `o3`).
- **Non-Intrusive Feature Onboarding Modal**:
  - Added `NewFeatureModal` that triggers once on first visit after browsing for 30 seconds.
  - Automatically skipped if the user is already on `/skills` or `/admin`, and permanently dismissed once acknowledged.

## [3.7.53] - 2026-09-08

### Added

- **Community Skills & Degradation Benchmark Lab** (`/skills`, `/skills/[slug]`):
  - Added public interactive community skills and model degradation detection arena.
  - Hosted 6 real-world benchmark HTML outputs (GPT-6-Astra 满血/降智, GPT-5.6 调教/裸跑, Gemini 3.8 Flash, 猪八戒骑自行车) in sandboxed live preview arena (`PelicanArena`).
  - Added 11 seeded community skills & benchmarks with original GitHub authors, star counts, install commands, tags, and rich documentation.
  - Linked each skill to relevant AI products (ChatGPT Plus, Claude Pro, Codex) with real-time price comparison cards for high-intent conversion.
- **Admin Skills CMS Management**:
  - Full CRUD management in admin dashboard (`/admin`) for publishing, editing, pinning, and toggling visibility of skills, degradation benchmarks, and community articles.
  - Added copy prompt tracking and view count analytics.

## [3.7.52] - 2026-09-07

### Changed

- Prioritized the lowest in-stock price as the group card's outside display price, aligning with the representative lowest-price offer.
- Arranged all offers within an offer group in strict ascending order by price (with in-stock preferred on equal prices), both in the API and frontend components.

## [3.7.51] - 2026-09-07

### Added

- Added `POST /api/v1/admin/source-candidates/cleanup` endpoint to purge invalid candidates (`no_match`, `validation_failed`, `disabled`, `rejected`) while strictly protecting promoted candidates and source intakes.
- Added "清理无效候选" (Batch Cleanup Invalid Candidates) button with confirmation prompt and execution feedback in the admin Source Discovery panel.

## [3.7.50] - 2026-09-07

### Added

- Added Business Cooperation & Advertising page (`/advertise`) and official contact email (`info@ai.pricememo.cn`).
- Added backend `SystemSetting` key-value model and admin API endpoints (`GET /api/v1/admin/settings`, `PATCH /api/v1/admin/settings`).
- Added admin panel toggle switch for `advertise_enabled` to dynamically control public visibility of commercial cooperation links and gate `/advertise`.

## [3.7.49] - 2026-09-05

### Fixed

- Kept Dujiao-Next discovery disabled in complete remote refreshes unless explicitly enabled.

## [3.7.48] - 2026-09-05

### Fixed

- Made the production Importer image use the configured Python package mirror so dependency installation is reproducible during deployment.

## [3.7.47] - 2026-09-05

### Fixed

- Preserve failed crawler discovery batches for a retry instead of silently dropping candidates.

## [3.7.46] - 2026-09-05

### Fixed

- Hardened admin and worker authentication, email delivery, source-intake state transitions, and notification retries.
- Prevented hidden, stale, unpublished, disabled-platform, non-finite-price, and cross-product data from leaking into public catalog and history responses.
- Tightened classifier, discovery, JSON-LD/XML parsing, crawler budgets, and pipeline input validation without re-enabling disabled Dujiao-Next publication.
- Fixed Web API error handling, watchlist bounds, public-source URL checks, mobile navigation, and visible focus states.
- Guarded PostgreSQL restore database names against identifier truncation.

## [3.7.41] - 2026-09-05

### Fixed

- **Accurate Product Classification for Free Accounts and Tools**:
  - Cleanly stripped exclusion phrases (`除Codex`, `不可codex`, `除Plus`, etc.) in brand and tier detection, ensuring titles like `(可网页反代，除Codex)` are not misidentified as Codex/Plus.
  - Expanded `CHATGPT_FREE_MARKERS` to recognize `g free`, `g-free`, `gfree`, `codex free`, `outlook/icloud/gmail free`, `free账密`, `free成品`, `free底号`, `可升级plus`, `开plus专用`, `好底号`, `未绑卡`, and correctly route them to `chatgpt-account` instead of `chatgpt-plus`.
  - Prevented session relay indicators (`反代专用`) from overriding free account markers.
  - Added payment link tools and verification CDK markers (`提炼`, `代提链`, `直卡支付链接`, `支付链接`, `卡头开通plus必备`, `提炼cdk`, `实卡号码`, `无限接马`) to classify into `chatgpt-access-service`.
  - Enforced a price safeguard for `chatgpt-plus` (< 8.00 CNY): demotes free helper accounts to `chatgpt-account`, helper tools/links to `chatgpt-access-service`, and flags abnormal low prices.
  - Synchronized classifier rules between `apps/api/app/services/classifier.py` and `pipeline/common.py`.

## [3.7.40] - 2026-09-05

### Added

- **Admin Offer Sorting Aligned with Frontend**:
  - `GET /api/v1/admin/offers` defaults to `sort="frontend"`, matching the public site ranking (`in_stock desc`, `cny_first`, `price asc`, `observed_at desc`).
  - Added sort selector in the admin search & filter bar with options for frontend default, latest updated (`updated_desc`), price low-to-high (`price_asc`), and price high-to-low (`price_desc`).
- **Admin Real-time Brand and Product Offer Counts**:
  - `GET /api/v1/admin/stats` now calculates and returns `product_counts` (by product slug) and `brand_counts` (by brand platform) across all active, public offers.
  - Added real-time count badges to each Brand Chip and Product Chip in the admin navigation rails.
  - Returns `X-Total-Count` header in `GET /api/v1/admin/offers` to report exact matching offer count.
  - Displayed `共 {offerTotal} 条报价（已载入前 {offers.length} 条）` summary header and added bottom pagination ("加载更多报价") so large product sets can be fully explored.
- **Catalog Alignment**:
  - Added `chatgpt-pro` (ChatGPT Pro) to `PRODUCT_TABS.OpenAI` in `apps/web/lib/catalog.ts`.

### Fixed

- **Prevent Scroll-to-Top on Admin Approval and Status Actions**:
  - Implemented optimistic in-place state updates for offer actions (`patchOffer`, `reclassifySingleOffer`) to prevent DOM node unmounting and focus loss.
  - Added `preserveScroll` helper to lock and restore window scroll coordinates (`window.scrollY`) across all administrative updates (offers, shop intakes, user reports).
  - Explicitly marked all action buttons with `type="button"` and blurred active elements prior to asynchronous state updates.

## [3.7.39] - 2026-09-05

### Added

- **Admin Category Hierarchy Aligned with Frontend**:
  - Replaced the admin offers panel's flat product slug list with a brand and product rail matching the public catalog (`apps/web/lib/catalog.ts`).
  - Added dedicated navigation views for `🚫 受限/已隐藏` and `❓ 未分类商品` with real-time offer count badges.
  - Added `brand` parameter filtering in `GET /api/v1/admin/offers` and enriched offer responses with `brand` and `product_name`.
  - Added grouped `<optgroup>` selection by brand hierarchy for offer reclassification.
  - Clearly highlighted restriction reasons for restricted/hidden offers with one-click restore (`恢复公开`) and hide (`隐藏/限制`) actions.

### Changed

- **Paused Dujiao-Next Candidate Discovery & Web Submission**:
  - Paused automatic Dujiao-Next discovery in remote refresh scripts (`ENABLE_DUJIAO_DISCOVERY=false`) and removed `dujiao-next` search queries from GitHub discovery.
  - Disabled the Dujiao-Next option on the public shop submission form (`/shops/submit`) with `(暂停收录)` badge.
  - Filtered out `dujiao_next` from the frontend catalog source platform filters.
  - Documented discovery pause and frontend disabled status in `docs/CONNECTORS.md`.

## [3.7.38] - 2026-09-04

### Changed

- **Include Shop Address and Name in Intake Notification Emails**:
  - Added merchant's original shop URL (`店铺地址：{source_url}`) and shop name (`店铺名称：{shop_name}`) to all applicant notification emails:
    - Auto-approval notifications (`shop_request.approved`)
    - Manual approval notifications (`shop_request.approved`)
    - Shop onboarding & publish notifications (`shop_intake.onboarded`), clearly distinguishing the merchant's `店铺地址` and `本站收录页面`
    - Rejection notifications (`shop_request.rejected`)
    - Scan completion with no products (`shop_intake.no_products`) and validation failures (`shop_intake.validation_failed`)
  - Ensures merchants can immediately identify which shop request has been processed and follow the links directly.

## [3.7.37] - 2026-09-04

### Fixed

- **Phone Verification Services Included in Benchmark Comparable Pricing**:
  - Added `verification_service` (`手机接码`, `实卡接码`, `短信验证`) to `COMPARABLE_DELIVERY_TYPES` (`is_comparable=True`).
  - Fixes issue where the dedicated `ChatGPT 手机接码` (`chatgpt-access-service`) product page displayed 0 offers and "暂无有货价" by default because `offerQuery` filters for `comparable=true`.

## [3.7.36] - 2026-09-04

### Changed

- **Reverse-Proxy Tokens Included in Benchmark Pricing**:
  - Included `session_token` delivery type (`只能反代`, `仅反代`, `无账号密码`, `发CDK不可网页`) into `COMPARABLE_DELIVERY_TYPES`.
  - Reverse-proxy token accounts now participate in comparable pricing calculations (`is_comparable=True`) as a recognized account delivery mode.

## [3.7.35] - 2026-09-04

### Fixed

- **Plus Account & SMS Service Precision Classification**:
  - Eliminated false routing into `chatgpt-access-service` caused by substring matching of `接马` inside account status markers (`未接马`, `需自行接马`, `自行接马`, `免接马`).
  - Removed legacy `GENERIC_EMAIL_MARKERS` (Gmail, iCloud) fallback from `chatgpt-access-service`, ensuring accounts with iCloud/Gmail emails (e.g. `韩国-PLUS-icloud邮箱`, `GP Plus gmail越南渠道`) correctly classify as `chatgpt-plus`.
  - Added support for `team` / `周限额` in implicit brand detection so `长效周限额team` routes accurately to `chatgpt-k12`.
  - Enhanced delivery type detection: `未接码`/`未接马` recognized as `semi_finished_account` (半成品/首登号), `icloud` and `保首登` recognized as `finished_account` (成品号).

## [3.7.34] - 2026-09-04

### Changed

- **Codex Classification Merged into ChatGPT Plus & Respective Tiers**:
  - Eliminated the top-level `brand == "codex"` prefix hijacking that forced all Codex-tagged items into `codex-access`.
  - Reclassified Codex accounts into their true underlying tiers: `chatgpt-plus` (for Plus/Sub2API/RT/CPA), `chatgpt-go` (for Codex Go), `chatgpt-k12` (for Team), and `chatgpt-account` (for Free).
  - Preserved `Codex`, `Sub2API`, `带RT` as scenario tags.
- **Dedicated SMS Verification ("手机接码") Category**:
  - Differentiated account attribute markers (`已接码`, `已接马`, `已绑手机`) from independent verification services (`代接码`, `手机接码`, `实卡接码`, `接码卡密`).
  - Allowed SMS verification services through classifier and renamed public frontend tab `辅助服务` to `手机接码`.
  - Removed `Codex` standalone tab from OpenAI navigation header.

## [3.7.33] - 2026-09-04

### Security

- **CRLF & Email Header Injection Protection**:
  - Sanitized `subject`, `recipient`, and `dedupe_key` across the outbox notification pipeline (`apps/api/app/services/source_intake.py` and `apps/api/app/services/outbox.py`).
  - Added strict email format validation in `ShopRequestCreate` forbidding CRLF, control characters, commas, and quotes.
  - Added strict sanitization to `shop_name` and `note` stripping all control characters and angle brackets to prevent header and template injection.
- **SSRF Hardening**:
  - Strengthened `normalize_public_https_url` in `apps/api/app/services/source_platform.py` to forbid internal hostnames, loopback/private/link-local/multicast IPs, and internal TLD suffixes (`.local`, `.internal`, `.lan`, `.home`, `.corp`, `.intranet`, `.priv`, `.arpa`).
  - Verified parameterized SQL queries across all repositories.

## [3.7.32] - 2026-09-04

### Added

- **Automatic Shop Intake Approval**: Enabled automated shop intake approval via `SHOP_INTAKE_AUTO_APPROVE` (`True` in production). When a store request completes automated security and platform detection (`ldxp`, `dujiao_next`, `woocommerce`, `16688`, `merchant_json`, `schema_org`), it is automatically approved into the worker validation/publishing queue without requiring manual admin intervention.
- **Admin Auto-Approval Email Notifications**: Automatically dispatches a notification email (`shop_request.auto_approved.admin`) to configured administrator emails (`SHOP_INTAKE_ADMIN_EMAILS`) whenever a shop request is automatically approved, providing full store details, detected platform, and direct links to the admin console.

### Changed

- **Applicant Notification**: Added explicit notifications to applicants confirming automatic approval upon successful probe detection.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.32` after CI passes.
- Rebuild and restart `api`.
- Set `SHOP_INTAKE_AUTO_APPROVE=true` in `.env` on production.

## [3.7.31] - 2026-09-04

### Added

- **Admin Shop Intake Platform Modification & Manual Approval**: Added platform selection dropdown to the admin console shop intake view (`POST /api/v1/admin/source-intakes/{id}/platform`), allowing administrators to switch an intake's platform type directly (e.g. from `other` to `ldxp`, `dujiao_next`, `16688`, `woocommerce`, `merchant_json`, `schema_org`).
- **On-Demand Platform Re-Detection**: Added `POST /api/v1/admin/source-intakes/{id}/redetect` to re-trigger automatic platform detection for an intake using the latest detection rules.
- **Intelligent Platform Auto-Upgrade on Approval**: Enhanced `POST /api/v1/admin/source-intakes/{id}/approve` to automatically recognize supported platform URLs (such as `wzyp.cn` -> `ldxp`) and approve them directly without throwing 409 errors.

### Fixed

- **Source Detector LDXP Domain Coverage**: Updated `detector/probe.py` to include `wzyp.cn` and `www.wzyp.cn` in `LDXP_HOSTS`, preventing new store applications on `wzyp.cn` (like shop `#37`) from being misclassified as `其他独立站` (`other`).

### Safety and data scope

- No database schema migrations required.
- Existing and future `wzyp.cn` shop intakes can be approved and validated seamlessly.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.31` after CI passes.
- Rebuild `api`, `web`, and `source-detector`.

## [3.7.30] - 2026-09-03

### Fixed

- **Detail-Driven Classification & Brand Detection**: Enabled brand and tier recognition fallback to product detail page descriptions (`raw_products.raw_json->>'description'`) when storefront titles are cryptic or non-standard.
- **Universal Non-Product Exclusion**: Systematically rejected pure tutorials (`教程`, `保姆教程`, `图文教程`, `反代教程`), test items (`测试商品`, `不要拍`, `不可拍`), SMS verification ad services (`接码渠道`), virtual cards (`虚拟卡`, `0刀卡`), and referral boost links from being classified into subscription products.
- **Reverse Proxy / Sub2API Token Isolation**: Offers offering only Sub2API/RT JSON tokens without login credentials (`只能反代`, `无账号密码`) are now correctly classified as `codex-access` (`session_token`) rather than `chatgpt-plus`.
- **ChatGPT Pro Integrity**: Filtered out team bug sub-accounts (`Team bug 子号`) and API quota credits (`20X 额度｜50美金`) from `chatgpt-pro` and `chatgpt-pro-20x`.
- **Multi-User Carpool Isolation**: Expanded `SHARED_POOL_MARKERS` to catch `拼车`, `共享账号`, `多人共享`, and `车位`, ensuring carpool offers are tagged `shared_pool` and `is_comparable = false`, preventing them from distorting individual account comparison prices.
- **Category Group False Positives**: Preserved genuine subscriptions in merchant storefront categories ending in `分组` (e.g. `Grok分组`).

### Safety and data scope

- Synchronized `apps/api/app/services/classifier.py` and `pipeline/common.py`.
- No database schema migrations required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.30` after CI passes.
- Rebuild `api`, `web`, and `importer`.

## [3.7.29] - 2026-09-03

### Added

- Added admin console tabs for reviewing restricted (`status=restricted`) and unclassified (`status=unclassified`) offers, with live count badges on the stats bar.
- Added admin search and target product filter to the offer management table.
- Added support for manual reclassification (including unclassifying back to `None`) and single-offer auto-reclassification via `POST /api/v1/admin/offers/{id}/reclassify`.
- Added visual display of merchant original category and restriction / hidden reasons in the admin offer view.

### Fixed

- Strengthened classifier and pipeline normalization to reject API relay groups (e.g. `plus分组`), relay model channels (e.g. `(cx,5,4)`), and non-20 dollar credit quotas from being falsely classified as `chatgpt-plus`, `chatgpt-pro`, or `codex-access`.

### Safety and data scope

- No schema migrations required.
- Existing restricted offers can now be inspected, audited, and reclassified directly from `/admin`.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.29` after CI passes.
- Rebuild `api`, `web`, and `importer`.

## [3.7.28] - 2026-09-03

### Added

- Added support for `wzyp.cn` and `www.wzyp.cn` storefront hostnames in the `ldxp` platform detector and crawler normalization.
- Added `https://wzyp.cn/shop/KFLA` to public source discovery seeds and crawler candidate database.
- Added `wzyp.cn` guidance to source intake copy in the web application.

### Safety and data scope

- Preserves `token.casefold()` as `source_key` and `token` as `shop_token` under the `ldxp` platform namespace.
- No database migration is required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.28` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.

## [3.7.24] - 2026-08-28

### Fixed

- Preserved the flat token-list contract of `GET /api/v1/shops` and added a paginated shop-card endpoint for directory pages.
- Excluded hidden products and shops without current public offers from public metadata, source pages, and sitemap entries; added pagination for shop directories.
- Unified API and pipeline 16688 classification with source-category context, rejected non-product aliases, and retained valid API-credit classification.
- Rotated 16688 discovery categories within the global page budget so one category cannot starve the others.

### Safety and data scope

- The 16688 default approval behavior is unchanged: newly discovered offers still follow the existing approval policy.
- No database migration is required.

### Deployment

- Follow `docs/QUICK_DEPLOY.md` and deploy only tag `v3.7.24` after CI passes.
- Rebuild `api`, `source-detector`, `web`, `importer`, and `crawler`.
- Run one complete multi-source refresh because the release changes crawler and pipeline behavior.

## [3.7.21] - 2026-08-27

### Fixed

- Enforced attempt matching before accepting an idempotent LDXP onboarding response, so a stale onboarding report cannot be mistaken for a retry of the current attempt.

## [3.7.20] - 2026-08-27

### Fixed

- Prevented completed LDXP intake attempts from being re-reported on later inventory scans, eliminating false production `409` errors while retaining the metadata required for publication onboarding.
- Made same-attempt scan-result retries idempotent after an intake reaches a closed state; a newer attempt remains rejected as stale.
- Restored LDXP application onboarding after a successful atomic multi-source snapshot, so validated applications with public offers are marked as published.

## [3.7.19] - 2026-08-27

### Fixed

- 16688 discovery now uses the platform's public AI source marketplace to resolve public goods to canonical `/shop/{shop_no}` URLs before the existing detector and review flow.
- Unified source discovery now runs before legacy Dujiao revalidation, and the 16688 and Common Crawl adapters run before the high-volume Bing adapter so Bing cannot consume their discovery opportunity.

## [3.7.17] - 2026-08-27

### Fixed

- Updated Common Crawl discovery regression coverage for the new platform-reserved budget semantics.

## [3.7.16] - 2026-08-27

### Fixed

- Scheduled unified source discovery now obtains its worker key inside the Compose crawler container instead of incorrectly requiring the systemd host service to load the production `.env`.
- Common Crawl discovery reserves candidate capacity for 16688, so high-volume LDXP URLs cannot consume the complete run budget before 16688 shop paths are queried.

## [3.7.15] - 2026-08-27

### Fixed

- The isolated source detector now falls back to another already-validated public DNS address when an initial socket connection fails, allowing 16688 sources to work on IPv4-only egress networks that resolve IPv6 first.
- A successful fallback address is pinned for the rest of the detection run without re-resolving DNS or weakening the existing public-address and TLS hostname checks.

## [3.7.14] - 2026-08-27

### Added

- Added public 16688 shop intake, source detection, approval, atomic publication, and the `16688` connector for public shop and goods APIs.
- Normalized 16688 aliases such as `/shop/HARVEY` to the canonical shop number and scoped shop tokens and product keys by platform so same-named shops do not collide.
- Extended automatic discovery through Bing and Common Crawl for 16688 shop URLs, while keeping discovery auto-approval disabled by default.

### Changed

- Added the v11 database constraint migration for 16688 source intakes and discovery candidates.

## [3.7.13] - 2026-08-22

### Changed

- Refreshed the full Web experience with the Signal Ledger visual system, clearer hierarchy, more consistent typography, responsive layouts, and unified interaction states.
- Reworked public-facing copy to describe observed prices and data freshness more precisely across product, guide, watchlist, submission, policy, and administration surfaces.
- Connected catalog search terms to the public catalog API and preserved available offers when product metadata is incomplete.

## [3.7.12] - 2026-08-22

### Fixed

- Each shop scan now runs inside a supervised browser Worker with a hard wall-clock deadline. A wedged Playwright page or renderer is terminated with its Chromium process group, recorded as a transient failure, and scanning continues with a fresh browser.

## [3.7.11] - 2026-08-20

### Fixed

- The crawler now stores only current matches and run summaries. The unused per-scan `product_snapshots` history no longer grows the operational SQLite database and delays each publication copy.
- Ten-minute inventory refreshes now update only LDXP data while carrying other published sources forward, so a transient external-source timeout cannot block inventory publication.

## [3.7.10] - 2026-08-20

### Fixed

- Compact publication uses a deferred SQLite transaction so the production SQLite runtime does not request a write lock on the attached read-only crawler database.

## [3.7.9] - 2026-08-20

### Fixed

- The compact crawler publication helper now runs on the production host's Python 3.6 runtime.

## [3.7.8] - 2026-08-20

### Fixed

- Scheduled publication now copies only the three current crawler tables used by the publisher instead of validating, copying, and revalidating the full multi-gigabyte history database on every refresh.

## [3.7.7] - 2026-08-20

### Fixed

- Persistent Chromium teardown now stops the Playwright connection directly instead of waiting indefinitely for `BrowserContext.close()` after all shops were scanned.

## [3.7.6] - 2026-08-20

### Fixed

- Browser-replayed shop API requests now abort at the configured crawler timeout instead of allowing one unresponsive source to block every later scan and publication.
- Browser refreshes remove stale Chromium singleton symlinks left by a terminated crawler, and inventory refreshes receive a one-hour service budget so a completed scan can finish atomic publication.
- Release metadata is aligned on `3.7.6` across the API, Web package, lockfile, and repository version marker.

## [3.7.4] - 2026-08-08

### Fixed

- Restored text and icon color utilities on form controls so dark action buttons remain readable.

## [3.7.3] - 2026-08-08

### Changed

- Redesigned the Web pages around a unified product, catalog, offer, guide, and source-review UI system.
- Reworked public copy to distinguish current observations from live data, separate empty and unavailable states, and remove internal workflow wording from user-facing surfaces.
- Clarified watchlist/Atom subscription behavior, correction privacy, offer grouping, information coverage, and source intake outcomes.
- Restored the public author-support entry and kept the existing community prompt wording unchanged.

### Fixed

- Restored support QR configuration defaults for local and production Web builds.
- Updated admin actions and source-discovery labels so buttons describe the action instead of repeating the current state.

## [3.7.2] - 2026-08-06

### Fixed

- LDXP sources in `blocked` or `challenge_required` no longer remain permanently excluded after a transient source-level challenge.
- Blocked sources receive bounded retry times and can be forced immediately with `--retry-blocked`; consecutive source-level failures still stop the scan through the existing circuit breaker.
- Regression coverage now verifies that an all-blocked batch is recorded as failed rather than successful.

### Changed

- Crawler self-tests and pytest coverage now run in CI.

## [3.7.0] - unreleased

### Added

- Unified source discovery engine: seed/Bing/GitHub/Common Crawl adapters submit normalized candidates to a PostgreSQL candidate pool (`source_discovery_runs`, `source_candidates`, v10 migration).
- Source Detector qualification of discovered candidates with bounded public samples and AI product classification, plus strict auto-approval for Dujiao-Next and WooCommerce and manual review for Schema.org and Merchant JSON.
- Internal candidate claim/lease/result APIs, idempotent promotion into `source_intakes`, and admin discovery funnel/controls.
- Production Dujiao discovery now runs GitHub sources with optional token, full AI keywords, and env-driven budgets.

## [3.6.0] - 2026-08-03

### Added

- WooCommerce Store API connector with exact minor-unit pricing, complete pagination validation, and safe variation fallback.
- Schema.org sitemap and product-page JSON-LD connector with bounded discovery and same-origin HTTPS validation.
- Dujiao-Next qualified candidates are auto-approved, and GitHub public repository homepages are a new passive discovery source.
- Source intake, detector, pipeline publication, Web labels, and a v9 database migration for the new source platforms.

### Changed

- Detector platform probing order is now Dujiao-Next, WooCommerce, Merchant JSON, then Schema.org.
- Directly submitted sitemap and product-page URLs are preserved exactly through detection and publication.
- WooCommerce products that are not purchasable never count as in-stock or enter lowest-price comparisons.

## [3.5.0] - 2026-08-03

## [3.5.0] - 2026-08-03

### Added

- Dujiao-Next connector support with brand-aware shop metadata, paginated products, variants, currency preservation, and reviewed-source publication.
- Public-fingerprint discovery with bounded candidate quotas, stale revalidation, isolated platform detection, and administrator-controlled intake routing.
- Merchant JSON intake publication and persistent multi-source refresh across LDXP, Dujiao-Next, and approved merchant feeds.

### Changed

- Complete catalog publication is atomic across all sources and now runs in the dedicated Importer image.
- Intake publication distinguishes raw records, classified offers, and fresh public offers; only a truly visible offer marks a source as published.
- Published sources remain in later complete refreshes, while disabled or review-required sources leave the next snapshot.
- Product brand and source platform are exposed separately across the API and Web application.

### Security

- Detector, Pipeline connectors, and Dujiao discovery share a bounded HTTPS client that pins validated public IPs while preserving TLS SNI and certificate verification.
- Public intake submissions no longer fetch user-controlled URLs inside the API process; the Detector has no database credentials or default-network access.
- Merchant feed shop identity is derived from the canonical feed URL, and public shop/product links reject credentials, fragments, control characters, and non-HTTPS schemes.
- Detector egress is designed for a production firewall policy that permits only public TCP/443 destinations.

## [3.4.0] - 2026-08-02

### Added

- Optional GitHub Star and author-support entry points in the public footer.
- Low-frequency, session-aware community prompts that stay disabled on administrator and shop-submission routes.
- Accessible WeChat Pay and Alipay support dialog with keyboard dismissal and mobile layouts.

### Changed

- Production Web containers can mount support QR images from `data/support` as read-only runtime assets.
- Production preflight validates both public HTTPS QR URLs whenever author support is enabled.

### Security

- Payment QR images and production support configuration remain outside the public Git repository.
- The support dialog does not display or configure a payee name and never records payment information.

## [3.3.1] - 2026-08-02

### Added

- Administrator intake emails now include a direct link to the matching review item in the admin panel.
- Final onboarding emails now include the published public shop page.

### Changed

- Admin intake links still require the administrator key, then scroll to and highlight the referenced request after authentication.

### Security

- Administrator links contain only the intake identifier and never include the administrator key.

## [3.3.0] - 2026-08-02

### Added

- Durable shop-intake records with explicit review, validation, onboarding, rejection, and retry states.
- Admin controls for approving, rejecting, retrying, and inspecting source-intake notification delivery.
- Applicant and administrator email notifications through Resend, with SMTP fallback and a transactional outbox worker.
- LDXP intake bridges for crawler and pipeline jobs, protected by a dedicated worker credential and leased claims.
- Idempotent `migrate_shop_intake_v6.py` migration for historical shop requests and notification outbox storage.

### Changed

- Shop submissions now require a valid contact email and return a stable request identifier for duplicate requests.
- Production preflight now requires administrator recipients, a separate intake-worker key, and a complete Resend or SMTP configuration.
- Production Compose and deployment guidance now include the notification worker and the v6 intake migration.

### Security

- Intake-worker access is isolated from the administrator API key.
- Source validation failures are sanitized before storage or email delivery.
- Resend credentials remain environment-only and are never written to application logs.

## [3.2.1] - 2026-07-30

### Changed

- Rewrote homepage, catalog, product-detail, About, methodology, shop, watchlist, and footer copy in user-facing language.
- Replaced internal pricing and crawler terminology with clearer descriptions such as recent in-stock low, common price, quote coverage, and source update status.
- Simplified grouped-offer labels, anomaly warnings, source links, update timestamps, and product FAQs without changing pricing or ranking behavior.

## [3.2.0] - 2026-07-29

### Added

- Official price references, verification dates, product data-quality scores, source scan-health facts, and daily aggregated price/stock trends.
- Browser-local watchlists and privacy-preserving Atom price/restock subscriptions.
- Public methodology, privacy, terms, security, developer, and correction-log pages.
- Public correction summaries with optional merchant responses while keeping reporter contacts private.
- Generic connector protocol, merchant HTTPS JSON Feed importer, submission flow, fixtures, and tests.
- Full delivery, period, warranty, fulfillment, freshness, stock, and price-range filters across catalog and product pages.

### Changed

- Default catalog ranking now prioritizes data quality and freshness before price.
- Homepage and directory counters use one published-snapshot scope and show trusted/comparable context.
- Price history presentation uses daily aggregates instead of connecting unrelated raw observations.
- Source-health labels explicitly describe crawler availability rather than merchant reputation.

### Security

- Merchant Feed submissions require public HTTPS URLs and reject localhost, internal hostnames, and private/reserved IP literals.
- Public correction endpoints exclude raw report messages and contact information.

## [3.1.0] - 2026-07-29

### Added

- Trusted-price scoring derived from comparable inventory and delivery-type medians.
- `trusted_offer_count` and `median_price` in public product responses.
- Per-offer `is_trusted_price` indicator while retaining anomaly warnings.
- API pricing unit tests and GitHub Actions checks for API and Web builds.
- Version, security, contribution, and release documentation.

### Changed

- Product cards and product details now use the trusted lowest price as the primary price.
- Extremely low or strongly off-median offers remain visible as source evidence but no longer lead the primary ranking.
- Related/all-in-stock lowest price remains available through `related_lowest_price` for backward compatibility.
- Homepage copy now distinguishes trustworthy rankings from raw low prices.
- Product structured data reports trusted offers rather than every comparable offer.

### Fixed

- Prevented ¥0.01 promotion, balance, trial, or restricted offers from becoming the headline price.
- Prevented anomalous representatives from being selected ahead of trustworthy offers inside grouped results.

## [3.0.0]

- Initial public architecture with FastAPI, Next.js, snapshots, classification, grouping, and price history.
