# 生产快速部署

这是 `ai.pricememo.cn` 的唯一标准部署流程。生产主机为 `pricememo-prod`，运行目录为 `/opt/ai-price-radar-v3`；主机没有 Git 和 Node.js，因此源码来自 Release Tag，Next.js standalone 必须在本机生成。

## 原则

- 只部署已发布且 CI 通过的 Tag，生产源码、API、Detector、Pipeline 和 Web 必须来自同一提交。
- 先暂停定时器，再等待当前刷新锁一次；部署完成前不要恢复定时器。
- 按改动范围重建服务：普通发布重建 `api`、`web` 和执行完整目录发布的 `importer`，来源检测或收录路由变更同时重建 `source-detector`，邮件代码变更同时重建 `notification-worker`，`crawler/` 或 Crawler Dockerfile 变更必须重建 `crawler`。`shared_http/` 变更必须同时重建 `source-detector`、`crawler` 和 `importer`。不重建 `db`，无迁移版本不得执行数据库结构操作。
- 部署前只做一次 PostgreSQL 备份，并保留旧 API/Web 镜像和旧源码包。
- 普通 API/Web 发布不等待完整爬虫刷新。只有改动 `crawler/`、`pipeline/` 或数据库结构时，才把一次完整刷新作为部署门禁。

## 1. 发布前检查

在仓库根目录确认工作区干净、Tag 指向当前提交，并完成完整门禁：

```powershell
$Tag = "vX.Y.Z"
$Version = $Tag.TrimStart("v")
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"

if (git status --porcelain) { throw "Working tree is not clean" }
if ((git rev-parse HEAD) -ne (git rev-list -n 1 $Tag)) { throw "HEAD does not match $Tag" }

Push-Location apps/api
python -m pytest -q
Pop-Location

npm --prefix apps/web ci
npm --prefix apps/web run typecheck
```

## 2. 暂停调度并创建回滚点

先停止三个 timer。若刷新锁忙，只等待当前任务；15 分钟仍未释放就中止部署并排查，不要强杀任务。

```bash
ssh pricememo-prod '
  systemctl stop \
    ai-price-radar-inventory.timer \
    ai-price-radar-refresh.timer \
    ai-price-radar-discover.timer

  deadline=$((SECONDS + 900))
  until flock -n /opt/ai-price-radar-v3/data/crawler/.refresh.lock -c true; do
    if (( SECONDS >= deadline )); then
      echo "refresh lock did not clear within 15 minutes" >&2
      exit 1
    fi
    sleep 5
  done

  cd /opt/ai-price-radar-v3
  bash scripts/backup_postgres.sh
'
```

然后保存旧源码和镜像。回滚名称必须带 `$Stamp`，部署记录中保留该值。

```bash
# 在服务器执行；将 STAMP 替换为本次值
cd /opt/ai-price-radar-v3
umask 077
tar -czf "backups/source_pre_deploy_STAMP.tar.gz" \
  --exclude=./backups --exclude=./data \
  --exclude=./apps/web/node_modules --exclude=./.env .
gzip -t "backups/source_pre_deploy_STAMP.tar.gz"

docker image tag "$(docker inspect -f '{{.Image}}' ai-price-radar-api-1)" \
  "ai-price-radar-api:rollback-STAMP"
docker image tag "$(docker inspect -f '{{.Image}}' ai-price-radar-web-1)" \
  "ai-price-radar-web:rollback-STAMP"

# 已经部署 source-detector 时执行；首次部署没有旧容器，记录为“不适用”
docker image tag "$(docker inspect -f '{{.Image}}' ai-price-radar-source-detector-1)" \
  "ai-price-radar-source-detector:rollback-STAMP"

# 本次改动 crawler/ 或 Crawler Dockerfile 时执行
docker image tag "$(docker image inspect -f '{{.Id}}' ai-price-radar-crawler:latest)" \
  "ai-price-radar-crawler:rollback-STAMP"
```

## 3. 本机构建并上传

必须注入生产 API 地址；构建后确认客户端静态文件不含 `http://localhost:8000`。

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "https://ai.pricememo.cn"
$env:NEXT_PUBLIC_SITE_NAME = "AI Price Radar"

# 启用支持作者功能时，这三项是公开的构建时配置，不是密钥。
$env:NEXT_PUBLIC_SUPPORT_ENABLED = "true"
$env:NEXT_PUBLIC_SUPPORT_WECHAT_QR_URL = "https://ai.pricememo.cn/support/wechat.jpg"
$env:NEXT_PUBLIC_SUPPORT_ALIPAY_QR_URL = "https://ai.pricememo.cn/support/alipay.jpg"

npm --prefix apps/web run build

if (rg -a -l "http://localhost:8000" apps/web/.next/static) {
  throw "Production client bundle contains localhost API URL"
}

$Source = "$env:TEMP\ai-price-radar-$Version-source-$Stamp.tar.gz"
$Web = "$env:TEMP\ai-price-radar-$Version-web-$Stamp.tar.gz"

git archive --format=tar.gz --prefix="ai-price-radar-$Version/" --output=$Source $Tag
tar -czf $Web -C apps/web .next/standalone .next/static
Get-FileHash $Source,$Web -Algorithm SHA256

scp $Source "pricememo-prod:/tmp/"
scp $Web "pricememo-prod:/tmp/"
scp "C:\Users\59908\Pictures\wechat.jpg" "pricememo-prod:/tmp/wechat.jpg"
scp "C:\Users\59908\Pictures\alipay.jpg" "pricememo-prod:/tmp/alipay.jpg"
```

## 4. Staging 校验、构建和切换

在独立 staging 目录校验 SHA-256、解包、复制生产 `.env`，运行 `production_preflight.py` 和 Compose 配置检查。全部通过后才覆盖运行目录。

```text
1. sha256sum -c 检查两个上传包
2. 解压源码到 /opt/ai-price-radar-staging-$Stamp
3. 解压 .next/standalone 和 .next/static
4. 从当前运行目录复制 .env；确认新增的 `DETECTOR_WORKER_KEY` 至少 32 字节，且不同于 Admin/Intake Worker Key
5. python3 scripts/production_preflight.py
6. docker compose ... config -q；确认 `source-detector` 没有数据库凭据、默认网络或 Docker socket
7. 覆盖 /opt/ai-price-radar-v3，但保留 .env、data/、backups/
8. 创建 `/opt/ai-price-radar-v3/data/support`，将两个二维码安装为 `wechat.jpg` 和 `alipay.jpg`，目录权限设为 `755`、文件权限设为 `644`
```

随后构建并依次切换 API、来源检测 Worker、Web：

```bash
cd /opt/ai-price-radar-v3
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.pricememo.yml"

$COMPOSE build api source-detector web
$COMPOSE build importer

# 本次改动邮件通知配置或 Worker 代码时，取消下一行注释后执行
# $COMPOSE build notification-worker

# 本次改动 crawler/ 或 Crawler Dockerfile 时必须执行
$COMPOSE build crawler

# Release Notes 要求迁移时，在切换 API 前用新 API 镜像执行；脚本名按版本替换。
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_productization_v5.py

# 店铺收录状态机与邮件 Outbox 迁移；重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_shop_intake_v6.py

# 报价历史币种迁移；在切换读取 offer_history.currency 的 API 前执行，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_currency_v7.py

# 来源自动识别与收录状态约束迁移；会把 merchant_feed 规范为 merchant_json，
# 合并同 URL 冲突记录；在切换读取新字段的 API 前执行，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_source_intake_v8.py

# 来源平台枚举迁移：允许 WooCommerce 与 Schema.org 独立站来源进入收录与发布流程；
# 在切换读取新平台字段的 API 前执行，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_source_platforms_v9.py

$COMPOSE up -d --no-deps api
# 等待 ai-price-radar-api-1 healthy，确认 /health 返回目标版本

$COMPOSE up -d --no-deps source-detector
# 确认 Worker 仅连接 detector_control/detector_egress，日志无持续领取或回报错误

$COMPOSE up -d --no-deps web
# 若本次发布包含邮件通知配置或 Worker 代码，同时取消下一行注释并切换 notification-worker
# $COMPOSE up -d --no-deps notification-worker
# 确认公网首页出现目标版本文案
```

API 失败时立即恢复旧 API 镜像；Web 失败时只恢复旧 Web 镜像。不要回滚或重建 PostgreSQL。

迁移必须先在临时数据库演练，并确认可重复执行。没有迁移要求的版本省略迁移命令，不能自行推断或新增数据库操作。

## 5. 固定验收

以下项目全部通过即视为部署完成：

```text
[ ] https://ai.pricememo.cn/health 返回 status=ok 和目标版本
[ ] API、Web、DB、source-detector 容器运行，API/DB 为 healthy
[ ] source-detector 不含 DATABASE_URL/Redis/Docker socket，且未加入默认数据库网络
[ ] OpenAPI 包含本版本新增字段
[ ] 新收录申请按 submitted → detecting → pending_review 流转；批准的 Dujiao/Merchant/WooCommerce/Schema.org 来源只有 public_offer_count > 0 才为 published
[ ] 已 published 且仍启用的 Dujiao/Merchant/WooCommerce/Schema.org 来源在连续两次完整刷新中都存在；disabled 来源在下一快照移除
[ ] 首页、报价目录和一个商品详情页可正常访问
[ ] 真实商品的可信最低价与 related_lowest_price 口径正确
[ ] API/Web 部署后日志无 traceback、exception、critical
[ ] 三个 systemd timer 已恢复为 active
[ ] 数据库备份、旧源码包和旧镜像回滚标签存在
[ ] 本次改动 crawler/ 时，新 Crawler 镜像已构建且旧镜像回滚标签存在
[ ] `ai-price-radar-importer` 已从当前 Tag 构建，且完整发布由该镜像执行
[ ] 本次改动 crawler/、pipeline/ 或数据库结构时，一次完整多来源发布结束，日志确认所有来源成功且 published=true
```

恢复定时器：

```bash
systemctl start \
  ai-price-radar-inventory.timer \
  ai-price-radar-refresh.timer \
  ai-price-radar-discover.timer
```

恢复后可能因 `Persistent=true` 立即补跑一次，这是正常调度。普通 API/Web 发布记录任务已启动即可，不要等待后续每个周期；涉及爬虫、数据管道或数据库结构的发布，才等待一次任务完成并确认 `failed=0`。

## 回滚

```bash
cd /opt/ai-price-radar-v3
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.pricememo.yml"

docker image tag ai-price-radar-api:rollback-STAMP ai-price-radar-api:latest
docker image tag ai-price-radar-web:rollback-STAMP ai-price-radar-web:latest
# 仅在部署前已保存 source-detector 回滚标签时执行下一行
docker image tag ai-price-radar-source-detector:rollback-STAMP ai-price-radar-source-detector:latest
$COMPOSE up -d --no-deps --force-recreate api source-detector web

# 本次发布改动 crawler/ 时同时恢复 Crawler 镜像
docker image tag ai-price-radar-crawler:rollback-STAMP ai-price-radar-crawler:latest
```

若发布同时修改了定时脚本、crawler 或 pipeline，再恢复 `backups/source_pre_deploy_STAMP.tar.gz` 中的源码。数据库仅在明确存在不兼容迁移且获得单独批准时恢复。
