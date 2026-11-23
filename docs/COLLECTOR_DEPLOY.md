# 独立采集节点

主站保存审核结果、任务队列、商品库、快照与通知。甲骨文只运行来源验证、发现、浏览器扫描和公开商品采集，不持有 DATABASE_URL、Admin Key、机器人密钥或用户数据。

独立的 `ldxp-shop-sync` 商户自动对接服务继续留在主站，商户账号与写入权限不迁入采集节点。它通过商户 API 取得实际商品与价格；现有 Radar Bridge 的市场参考价方法未被调用，扫描库仅用于补充固定核心搜索词，不参与实际调价。旧 SQLite 保留作为回滚状态，不能再把它当成实时采集库。

## 运行边界

- 主站定时器创建持久采集批次；Worker 主动领取，租约每 30 秒续期。断线不占用主站 HTTP 请求；过期租约可以重领，旧租约的回报被拒绝。
- 同时只允许一个目录批次进入采集/发布，防止旧的全量结果覆盖新库存。发现任务与目录批次分开，按队列调度，不新增 Redis/RabbitMQ。
- 甲骨文按来源保存已完成结果，重启后续跑；保留真实采集时间。结果分来源标记成功、暂时失败或明确下架；不将失败当作空商品列表。
- 采集结果经压缩上传到主站私有目录；主站限制压缩、解压和单条记录大小，核对任务身份、来源顺序、记录完整性与租约。目录发布重新检查审批与店铺可见性，沿用唯一发布器。
- PostgreSQL 中的任务记录可追踪等待、运行、已采集、发布中、已发布和失败；已发布批次不重复入库或推送。

## 网络与凭据

- 主站通过固定主机密钥验证的 SSH 专用连接，把仅供 Worker 使用的网关反向转发到甲骨文 Docker 网桥。SSH 专用账号禁止交互、SFTP、任意命令及其他端口转发；只允许指定监听地址和端口。
- Worker 网关只代理已有发现/验证/收录与新增采集任务接口，拒绝后台、登录、数据库及任意其他路径。公网 Caddy 保持拒绝 internal 路由。
- Worker 使用独立随机密钥；发现、验证、目录采集分别鉴权。密钥只读挂载，日志禁止记录密钥和浏览器会话。
- 采集 Docker 网段通过原子更新的 DOCKER-USER/INPUT 规则拒绝访问宿主机、RFC1918、link-local、IPv6 与云元数据；仅放行指定 Worker 网关。容器自己的 loopback 与宿主机隔离，不承载任何应用服务；浏览器访问域名沿用 LDXP 白名单。无 Docker socket、无宿主 PID、cap_drop ALL、no-new-privileges，运行非 root。
- PinnedHTTPSClient 继续验证公网 DNS/IP、TLS 和响应预算。16688 的各进程共用限速状态，403/429/520 触发冷却；不使用 IP 轮换或绕过证书检查。
- 公网出口仅允许 DNS 与 HTTP/HTTPS；同时拒绝主站、甲骨文公网 IP 的回连，防止云平台公网 NAT 绕过宿主机规则。启动时核对 Docker 网络名、桥接口、子网及 IPv6 状态，并把专用跳转原子移到父链首位；改 IP 时同步更新 `collector_firewall.py` 中的宿主地址。

## 切换门禁

1. 代码评审、测试、CI、干净 Tag 与 docs/QUICK_DEPLOY.md 发布流程全部完成。
2. 甲骨文先建独立目录与镜像，现有 Caddy/API 转发服务不改动。
   主站构建时加入 `-f docker-compose.collector-control.yml build collector-gateway`。v3.9.94 起使用移除文件能力标记的专用 Caddy 镜像，保持非 root、cap_drop ALL 和 no-new-privileges，不能直接用带 file capability 的官方二进制替代。v3.9.95 起网关使用专用 `ai-price-radar_collector_gateway` 桥，仅 API 加入该网络；不要把网关加入默认数据库网络或 Docker internal 网络。
3. 暂停主站旧扫描调度、等待当前刷新完成，再一致性备份 SQLite 和浏览器会话；保留原文件作为回滚点。
   主站结果目录预建为 root:10001、02770；甲骨文预建 `pricememo_collection` 外部网桥（`br-pm-collect`，172.30.93.0/24，网关 .1），先安装隔离规则再启动 Worker。
   停止旧审批入口使用后，将一致的 SQLite 副本与 merchant_sources.json 放到 root 所有的私有迁移目录，仅这两个文件只读挂载给新 importer，运行 `python collector_jobs.py import-approvals --crawler-db /legacy/approvals.db --merchant-sources /legacy/merchant_sources.json`（无 merchant 配置时省略该参数）。它只导入已经批准且主库不存在的来源，保留现有禁用决定和隐藏店铺，重复运行不重复创建。切换后审批统一在主站后台维护；旧 `review-dujiao` 与 merchant_sources.json 不再作为新采集流程的审批入口，仅用于旧调度回滚。日常调度不再读取或挂载旧采集库与浏览器会话。
   安装 `pricememo-collector-firewall.service` 和 `pricememo-collector.service`；Compose 禁用 Docker 自动重启，由 systemd 管理整个采集服务，每次启动重新检查防火墙，规则失败时禁止启动。不得直接设置 `restart: unless-stopped` 绕过这个顺序。
4. 分阶段迁移时，将 `COLLECTOR_LDXP_ENABLED=false` 写入主站环境：主站继续运行 `refresh_remote.sh ldxp-only`，只扫描和发布 LDXP；Oracle `collector-scan.timer` 只领取已批准的非 LDXP 来源。验证 16688、HTTP 来源、发现/验证回传、任务续租、断线恢复、未授权请求拒绝、SSRF/云元数据拒绝。LDXP 验证挑战完成后，才切换该开关并迁移浏览器扫描。
5. 分阶段切换时，先验收 Oracle 首轮非 LDXP 采集发布成功，随后恢复主站 inventory/refresh timer（refresh 使用 `ldxp-only` 扫描100家），主站 discover 仅运行 `ldxp-discover`。启用 `collector-scan.timer`、`collector-discover.timer` 和 `collector-publish.timer`。Oracle 环境设置 `COLLECTOR_LDXP_ENABLED=false`，不触碰 LDXP 浏览器。发布器只保留最近主站 LDXP 报价，并且仅允许跨越独立的 LDXP 快照重新发布 HTTP 来源，其他并发修改仍拒绝。
   v3.9.103 起必须同时迁移 16688 收录安全检测：主站 `.env` 配置 `DETECTOR_16688_ON_ORACLE=true`、`DETECTOR_SCOPE=other`，Oracle detector 使用 `DETECTOR_SCOPE=16688`。领取 API 按官方 URL 的真实域名划分申请和发现候选，不信任申请者填写的平台。旧主站 Worker 即使省略 scope 也不能领取 16688；商品采集、申请验证是两个进程，必须均验收。
   切换时先停止旧主站 detector，升级 API 并应用分流配置，再启动两地 detector。删除 Oracle 旧 `partial.conf` 中只启动 `collector` 的覆盖，使用 `up --no-build --abort-on-container-exit collector detector`，仍由防火墙依赖约束启动。主站 LDXP 扫描继续运行。检查 Oracle 日志显示目标 intake ID 验证成功、批准后有公开商品才转为 published；先前 validation_failed 的申请需经后台重新排队，不会仅因服务迁移自动变更审核结论。
   来源入队统一将域名转为 IDNA ASCII。切换前检查历史待检测 URL，若 Unicode/全角域名正规化后是官方 16688，仅更新该记录的 source_url/canonical_url 为正规 URL（保留候选主键与审核状态）；在新的过滤规则启用前完成，防止旧文本绕过分流。
6. 回滚时停甲骨文 Worker、回收租约并恢复旧调度；保留任务与结果，数据库和既有快照不回滚。
