# AI Price Radar v3 项目交接文档

- 项目版本：v3.0.0
- 文档版本：v1.2
- 编制日期：2026-07-25
- 项目包：`ai_price_radar_v3.0.0.zip`
- 项目状态：已部署并启用生产数据自动刷新

## 1. 交接摘要

AI Price Radar v3 是一个聚合公开 AI 订阅商品报价的平台。系统由 Next.js 前端、FastAPI API、PostgreSQL、链动小铺浏览器爬虫及数据同步管道组成。项目支持公开搜索、产品详情、店铺详情、报价历史、自动分类、举报纠错和基础管理后台。

当前代码已完成 Python 语法检查、API 单元测试、爬虫自检、导入锁测试和完整 `next build`。2026-07-26 已在目标服务器完成生产 Docker 构建、PostgreSQL 并发锁、HTTPS 签发、幂等导入、管理流程、举报限流、备份恢复和自动数据刷新验收，站点地址为 `https://ai.pricememo.cn`。

## 2. 当前范围

### 已包含
- Next.js 15 + React 19 + Tailwind CSS v4 前端
- FastAPI + SQLAlchemy 2 API
- PostgreSQL 16
- LDXP 浏览器爬虫 v2
- SQLite / CSV 导入
- OpenAI 产品族（ChatGPT、Codex、OpenAI API）、Claude、Gemini、Grok 商品标准化
- 标签与风险文字提取
- 当前报价和报价历史
- 产品、店铺、搜索筛选页面
- 管理密钥后台和举报处理
- Docker Compose、Windows 脚本、备份脚本

### 不包含
- OAuth、多用户与细粒度权限
- Alembic 数据库迁移
- 消息队列和分布式任务调度
- 自动验证码绕过
- 订单、支付、卡密和账户凭证存储
- 店铺信用评分或欺诈判定

## 3. 架构与数据流

```text
公共索引 / 种子 URL
        ↓
LDXP Playwright 浏览器爬虫
        ↓
ldxp_crawler.db（SQLite）
        ↓
完整性检查与 SQLite 快照
        ↓
sync_ldxp.py（自动）/ import_csv.py（历史数据）
        ↓
分类、标签、风险文字、幂等 Upsert
        ↓
PostgreSQL
        ↓
FastAPI
        ↓
Next.js 前端与管理后台
```

发布保障：失败的爬虫扫描不会删除网站最后一次成功数据；完整导入使用已发布快照在同一事务中原子切换，任一记录失败会回滚并继续展示上一快照；同一店铺和商品重复导入不会产生重复报价；价格、库存或状态发生变化时才新增历史记录；超过 72 小时的报价不再参与最低价计算。

## 4. 技术栈和关键版本

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15.4、React 19.1、Tailwind CSS 4.1、TypeScript 5.8、Motion、Phosphor Icons、Geist |
| API | FastAPI 0.115+、Uvicorn、SQLAlchemy 2、Pydantic Settings |
| 数据库 | PostgreSQL 16 Alpine |
| 数据管道 | Python、psycopg 3、SQLite |
| 爬虫 | Python、Playwright Chromium、requests |
| 部署 | Docker Compose、Nginx/Caddy/Cloudflare 可选 |

## 5. 目录职责

- `apps/web`：公开前端和 `/admin` 管理页面
- `apps/api`：公开 API、管理 API、模型、分类器和演示数据
- `crawler/ldxp`：店铺发现、浏览器验证、商品扫描和 SQLite 结果库
- `pipeline/sync_ldxp.py`：从爬虫 SQLite 幂等同步到 PostgreSQL
- `pipeline/import_csv.py`：从历史商品 CSV 导入
- `scripts/crawl_and_publish.sh`：扫描并发布
- `scripts/refresh_remote.sh`：生产发现、扫描、校验、备份和 PostgreSQL 同步
- `deploy/systemd`：生产周期任务单元
- `scripts/backup_postgres.sh`：PostgreSQL 压缩备份
- `docs`：架构、部署、数据政策和本文档

## 6. 环境变量

生产前必须修改：`POSTGRES_PASSWORD`、`ADMIN_API_KEY`、`PUBLIC_SITE_URL`、`WEB_ORIGIN`、`NEXT_PUBLIC_API_BASE_URL`。建议将 `SEED_DEMO_DATA` 设为 `false`。

管理密钥至少使用 32 字节随机值。不得把 `.env`、浏览器 profile、数据库备份或真实密钥提交到 Git。

## 7. 部署、验证与回滚

首次部署：复制 `.env.example` 为 `.env`，修改密钥和域名，然后执行 `docker compose up --build -d`。验证容器、健康检查、前台、后台、API 和数据库写入。

生产环境通过内置 Caddy 暴露 `/` 和 `/api/*`。默认 compose 不发布 PostgreSQL、API 或 Web 的宿主机端口；单独的开发 override 仅绑定 `127.0.0.1`。

回滚前先备份数据库。代码回滚使用上一版本项目包重新构建；如果数据库模型发生不兼容变化，则恢复对应版本的 PostgreSQL 备份。当前项目没有 Alembic，任何模型修改上线前都必须先设计迁移方案。

## 8. 数据采集和发布

首次爬取可能出现 Verification 页面，需要在真实浏览器中正常完成一次验证。项目不会绕过验证码。目标服务器会在 Xvfb 虚拟显示器中运行普通 Chromium；如需人工刷新会话，可按需启动只绑定 `127.0.0.1:6080` 的 `crawler-bootstrap`，并通过 SSH 隧道访问，不能把该端口发布到公网。

生产流程已自动化：扫描成功后先校验 SQLite，再生成保留 14 天的快照，最后幂等同步 PostgreSQL；不需要人工执行导入。若一轮没有任何成功店铺，任务会在生产导入前退出，保留线上最后一次成功数据。

当前 systemd 调度：

- 商品库存：每 10 分钟扫描已有命中商品的店铺，每轮最多 25 家。
- 常规扫描：每小时扫描候选店铺，每轮最多 100 家；候选按最早尝试时间轮转。
- 新店发现：每 12 小时运行一次，每轮最多保留 500 个候选；新候选由下一次常规扫描抓取并自动入库。

三类任务共享单实例文件锁，重叠任务会安全跳过；浏览器访问间隔保持 2 秒，连续 3 家被验证、阻断或限流时熔断。

2026-07-26 已将旧爬虫的 213 家候选合并到生产候选库，其中新增 198 家 Wayback 历史候选。候选由常规扫描按每轮最多 100 家轮转验证，不需要人工导入。

## 9. 数据库与业务规则

核心表：`shops`、`products`、`raw_products`、`offers`、`offer_history`、`scan_runs`、`reports`。

公开报价必须同时满足：报价 active、approved；店铺和产品可见；库存为 in_stock；价格大于 0；观察时间不超过 72 小时。

风险标签仅是从标题和描述中提取的事实文字，例如“无售后”“无质保”“售出不退”，不得展示为欺诈评分或未经证实的指控。

自动分类优先使用商品原始标题确认目标品牌，描述不能单独触发商品收录；在标题或原始分类已经确认 OpenAI 产品族后，描述只允许继续细化 Team/K12 和 Pro 倍率。ChatGPT、Codex 与 OpenAI API 统一归入 OpenAI 平台，其中 ChatGPT Free、Plus、Go、K12、Pro 5x、Pro 20x 为独立标准商品；Team、Business、团队邀请、车位、母号和自动拉均归入 K12，Free、Plus 与 Go 必须由标题明确触发，未明确标注 5x/20x 的 Pro 留在通用 Pro 分类，不猜测倍率。仅靠原始分类确认品牌时，标题还必须包含会员、订阅、充值、接码、API、成品账号等商品语境；普通 Gmail、Outlook、iCloud 邮箱不会因为位于 GPT/Gemini 分类下就公开。标题明确说明用于 ChatGPT/OpenAI 的接码、验证、提链或邮箱辅助商品会进入独立的“ChatGPT / Codex 周边服务”，不会混入 Plus 或账号价格；镜像站、教程、授权工具、加速器、网盘和小红书工具等非账号或订阅商品不公开。分类兼容 `chat plus`、`Open Ai`、`PULS`、`plsu` 以及带“成品/半成品/首登”语境的历史命名。Grok 与 SuperGrok 属于目标商品。

管理端“重新分类”会覆盖自动分类结果；新规则无法识别的报价会清空标准产品归属，因而立即退出公开产品和店铺报价列表。人工隐藏、审核状态仍由导入流程保留。

## 10. API 和前端

公开 API：产品列表、产品详情、店铺详情、筛选元数据、举报提交。产品和店铺详情报价会返回原始标题、原始分类、纯文本描述、商品类型、市场标价、首次/最后发现时间、价格、库存、交付方式和原站链接；原始 HTML、内部用户字段和联系方式结构不会直接输出。管理 API：统计、报价列表、报价修改、重新分类、举报列表和举报状态修改。管理员接口使用 `X-Admin-Key`。

报价目录采用带真实品牌图标的平台标签和标准商品标签两级快捷筛选，并支持交付形态、周期、质保、自动发货、更新时间、排除词和“仅显示可直接比较”筛选。标准产品主最低价只统计可直接比较报价，相关商品最低价单独展示。商品详情按同款指纹聚合，首屏仅返回 30 个同款组，滚动接近列表底部时继续分页；展开同款后再加载全部店铺报价和原始描述。每个公开页面标注已发布快照编号和北京时间。站点提供 canonical、robots.txt、sitemap.xml 和不含虚构评分的 Product / AggregateOffer 结构化数据。公开页不展示管理入口，管理页面仍可通过已知的 `/admin` 路径访问。

前端服务端请求默认缓存 60 秒，商品详情页同时使用 60 秒的 Next.js 整页增量缓存，因此数据导入后页面最多可能约 60 秒后更新。管理页面从浏览器直连 `NEXT_PUBLIC_API_BASE_URL`，生产环境必须确保 HTTPS、CORS 和 API 域名配置正确。

## 11. 管理后台操作

进入 `/admin`，输入管理密钥后加载数据。可以发布、隐藏、恢复报价，修正产品分类，重新运行分类器，处理举报。

隐藏报价时应填写原因；处理举报前应打开原始来源核验；不要删除数据库记录，以便保留审计轨迹。

## 12. 日常运维

每日：检查服务健康、扫描任务、失败率、待处理举报和数据库备份。

定时任务状态与日志：

```bash
systemctl list-timers --all 'ai-price-radar-*'
journalctl -u ai-price-radar-inventory.service -n 100 --no-pager
journalctl -u ai-price-radar-refresh.service -n 100 --no-pager
journalctl -u ai-price-radar-discover.service -n 100 --no-pager
```

每周：抽查来源链接和分类准确性，检查长期失效店铺，恢复演练抽样备份。

每月：更新依赖、检查磁盘、清理旧日志、复审数据政策和目标站点条款。

## 13. 备份和恢复

使用 `scripts/backup_postgres.sh` 生成 gzip 压缩 SQL。建议保留 7 份每日、4 份每周和 6 份每月备份，并至少保存一份异地备份。

恢复前暂停 API 和导入任务，在新数据库中演练恢复，不要直接覆盖唯一生产库。

## 14. 故障排查

- 前台打不开：检查 web 容器、3000 端口和反向代理。
- API 失败：检查 `/health`、数据库连接和 API 日志。
- 后台提示密钥无效：检查 `ADMIN_API_KEY` 与 `X-Admin-Key`。
- 没有报价：确认已导入数据、报价未过期、approved/active、库存状态和价格。
- 爬虫 403/验证：使用有头浏览器重新建立会话；不要提高并发或绕过验证。
- 导入无变化：可能是幂等机制正常工作；检查源数据的价格、库存、状态和时间是否变化。
- 页面更新延迟：Next.js 请求缓存为 60 秒。

## 15. 安全与合规

不要存储或发布卡密、账号密码、订单、支付信息、客户邮箱或私人聊天记录。生产环境应限制 `/admin`，对举报接口限流，关闭数据库公网端口，使用 HTTPS，分离爬虫与公网服务账号，并定期轮换管理密钥。

网站必须保留来源链接、更新时间、纠错入口和明确免责声明，不得声称第三方店铺为官方渠道。

## 16. 已知限制与技术债

1. 完整 `next build` 与目标服务器 Docker 镜像构建均已通过。
2. 数据库使用 `create_all`，没有 Alembic 迁移。
3. 后台仅使用静态 API Key，没有用户、会话、审计日志和 RBAC。
4. 管理页面产品分类选项目前为前端静态列表，已覆盖当前 OpenAI 产品族、Claude、Gemini 和 Grok 分类。
5. 演示数据现已默认关闭，本地演示需显式开启。
6. 开发 override 可在 `127.0.0.1:5432` 暴露数据库，不能用于生产。
7. 抓取覆盖率受公共索引、验证页面和目标站点变化影响，不能承诺全量。
8. 已有单机任务锁、systemd 自动调度和 journal 日志，暂无集中告警和指标系统。
9. 报价过期窗口固定为 72 小时，需根据扫描频率调整。
10. 举报接口已有按客户端的数据库限流；验证码和更强的边缘防滥用仍待补充。

## 17. 接收方验收清单

- 解压项目并核对文件完整性
- 配置生产 `.env`
- 完成 `docker compose up --build -d`
- 验证前台、API、后台和数据库
- 关闭演示数据
- 移除数据库公网端口
- 配置 HTTPS 和反向代理
- 导入一份真实爬虫数据库
- 验证重复导入不重复
- 验证隐藏、恢复、改分类和举报处理
- 执行备份并完成一次恢复演练
- 配置定时扫描、导入和备份
- 建立域名、服务器、DNS、密钥和备份的责任人

## 18. 后续优先级

P0：仓库侧与目标服务器验收、真实数据导入和周期扫描均已完成。仍需由运维配置 PostgreSQL 周期备份和异地保留。

P1：Alembic、OAuth/Cloudflare Access、管理审计日志、集中任务监控与告警、动态分类目录。

P2：SEO 内容管理、更多来源适配器、价格异常检测、店铺申诉工作流、搜索服务和数据分析。
