# Release Notes - v3.7.88

**发布日期**: 2026-09-18  
**发布版本**: `v3.7.88`

---

## 版本核心亮点

v3.7.88 是一次以**安全性加固、并发正确性与数据一致性**为核心的修复版本，覆盖后端 API、数据管道、机器人扩展与前端交互共 100+ 处问题。

### 1. 安全加固（高优先级）

- **QQ 登录后门封堵**：`mock=true` 模拟登录分支与 `/qq/scan-mock` 现由 `QQ_MOCK_AUTH_ENABLED` 显式开关控制（默认关闭），`QQ_AUTH_ENABLED=false` 时回调改为拒绝认证而非静默铸造真实会话。
- **OAuth state 校验**：登录入口将随机 `state` 绑定到浏览器 Cookie（`qq_oauth_state`，HttpOnly + Lax + 10 分钟），回调在交换授权码前做常数时间比对，阻止攻击者把自己的授权码植入受害者账号。
- **绑定接口越权修复**：新增 `complete_qq_binding_for_user`，手动绑定改为校验绑定会话归属当前登录用户并拒绝已被他人绑定的 target；`/notifications/bot/command` 不再信任请求体 `sender_id`，身份一律从当前用户绑定推导。
- **绑定码防重放**：已完成（BOUND）的绑定会话不再允许修改绑定；解绑时撤销该用户全部待绑定授权。
- **验证码防爆破**：`auth_codes` 新增 `attempts` 计数，连续错误达到 5 次即失效；验证接口按 IP 做滑动窗口限流；验证码消费改为原子 UPDATE，杜绝并发重放同一验证码换取多个会话。
- **凭据治理**：移除源码中硬编码的商户 token（`admin.py` / `sync_ldxp_coupons.py`），改为仅从 `LDXP_MERCHANT_TOKEN` 环境变量读取，缺失时明确失败；同步接口 token 由 URL Query 改为请求体，避免进入反代与访问日志。
- **日志脱敏**：生产日志不再输出登录验证码；控制台明文验证码仅在 `DEV_PRINT_AUTH_CODES=true` 时输出。
- **机器人凭据权限**：`qq_bot_login.mjs` 以 0600 写入 `accounts.json`、0700 限制状态目录。

### 2. 并发与数据一致性

- **优惠券发放串行化**：活动兑换先锁活动行再校验额度，`claimed_count` 改为原子条件 UPDATE；直兑券改为 `WHERE is_assigned=false` 的条件更新；幸运掉券增加用户级行锁与进程内互斥，24 小时限领与全局每日额度不再可被并发绕过。
- **点击计数原子化**：报价点击计数改为 SQL 原子自增；防抖检查与写入置于同一临界区，同一 IP 并发请求不会再重复计入。
- **在线时长统一结算**：新增 `settle_session_activity`，心跳、点击与退出登录共用同一基线（`session.last_active_at`）结算增量，修复「登录 10 分钟被记为 20 分钟」与「点击反而少计在线时长」。
- **启动迁移补列**：`db_migration.py` 幂等补齐 `offers.click_count` 与 `auth_codes.attempts`，老库升级无需手工执行脚本。

### 3. 数据管道与公开接口

- **快照导出与公开目录对齐**：导出沿用公开报价可见性规则（禁用来源、`hidden_reason`、过期报价），可信价统计加入 1 元绝对下限并对齐 `trusted_rows`，仅以 CNY 计算人民币指标，避免 USD 报价混入。
- **快照不可变**：已存在的快照文件不再被覆盖；仅当前已发布快照可更新 `latest.json`，历史归档需显式 `--allow-historical`。
- **导出目录可配置**：新增 `PUBLIC_DATA_DIR`，compose 中 api 以只读、importer 以读写共享 `apps/web/public/data`，修复容器内 `/data/*` 端点必然 404 的问题。
- **分类规则统一**：管道与 API 的 Cursor / 智谱关键词规则对齐，同一标题不再因入口不同而进入不同产品。

### 4. 机器人扩展

- **网关不再阻塞事件循环**：`qq_gateway.py` 的取 token、命令处理与消息发送全部经 `asyncio.to_thread` 卸载；心跳新增 ACK 跟踪与接收超时，半开连接可被检测并重连；同一 `app_id` 的凭据变更会重建连接任务。
- **投递语义修正**：广播与通用推送仅在确认发送成功后计数；Connector 扫码用户（凭据存于绑定）不再被无条件跳过；涨价事件不再渲染为「降价」文案；涨跌开关按事件过滤内容；去重键改为价格变动标识，后续再次降至同一价格仍可提醒。
- **消息健壮性**：Telegram HTML 全字段转义，超长报告按行分批（标签不截断）；聊天指令长前缀优先匹配（`查询 plus` / `搜索 claude` 恢复正常）。
- **桥接并发**：相同幂等键通过 in-flight Promise 合并，临时文件按进程/时间戳命名；账号重载串行化；IPv6 host 生成合法 URL。

### 5. 前端体验

- **关注清单缓存按账号隔离**：云端缓存迁移到 `watchlist:v1:user:<id>`，匿名待迁移数据独立存储，迁移失败项保留可重试；登录后以服务端清单为准，不再把缓存回写云端。
- **订阅设置不再互相覆盖**：新增 `updateUserSubscription` 合并当前配置后再提交，切换邮件渠道不会再清空目标价、切换机器人不会再重置邮件。
- **加载与登录体验**：管理面板子模块改用「已验证密钥」挂载并在验证成功后重新加载；用户搜索改为提交态驱动，清除搜索立即生效；关注清单商品加载失败可重试；登录弹窗补齐焦点管理与 Esc 关闭，发码期间锁定邮箱避免验证码错配。
- **券状态与文案**：卡包与用户详情券按「可使用 / 已核销 / 已过期」区分并禁用无效入口；锦鲤掉券文案不再承诺固定店铺与面额，领取后展示实际店铺。

### 6. 部署与路由

- **Next.js 代理修复**：`next.config.ts` 统一读取 `INTERNAL_API_BASE_URL`，默认指向 compose 服务名 `api:8000`，并在 Dockerfile 构建阶段传入（`rewrites()` 在构建期固化）。
- **路由冲突清理**：删除与 Route Handler 同路径的 `public/` 副本（`.well-known/price-radar.json`、`price-radar-v1.schema.json`、`price-radar-api.md`）。
- **公开 Schema 修正**：用 `oneOf` 区分快照文档与 `latest.json` 指针，指针不再因缺少 `products` 校验失败；`/data/*` 路由补齐 ETag / If-None-Match 与 304 转发。
- **快照路由后缀修复**：`/data/v1/snapshots/1234.json` 不再被清洗成 `1234json`。

---

## 升级与迁移说明

- 数据表结构升级：`offers` 表新增 `click_count`；`auth_codes` 表新增 `attempts`。
- 上述列由 `apps/api/app/services/db_migration.py` 在应用启动时自动安全幂等迁移，无需手动停机执行 SQL。
- 新增可选环境变量：
  - `INTERNAL_API_BASE_URL`（构建期 + 运行期，默认 `http://api:8000`）
  - `PUBLIC_DATA_DIR`（api 只读挂载、importer 读写，默认容器内 `/app/public-data`）
  - `LDXP_MERCHANT_TOKEN`（商户同步令牌，未配置时同步接口返回 400）
  - `QQ_MOCK_AUTH_ENABLED`、`DEV_PRINT_AUTH_CODES`（仅开发环境使用，生产保持关闭）
- 历史迁移脚本同步修复：`migrate_claude_subdivision_v15.py` 的 `--dry-run` 不再写库并尊重人工锁定；`migrate_shop_coupon_campaign_v18.py` / `migrate_coupon_shop_binding_v19.py` 正确解析 `sqlite://` 形式的 `--database-url`，且不再把外部店铺活动强行绑定到 pricememo。
