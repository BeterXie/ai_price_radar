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
$env:NEXT_PUBLIC_SITE_NAME = "AI Price Memory"

# 启用支持作者功能时，这三项是公开的构建时配置，不是密钥。
$env:NEXT_PUBLIC_SUPPORT_ENABLED = "true"
$env:NEXT_PUBLIC_SUPPORT_WECHAT_QR_URL = "https://ai.pricememo.cn/support/wechat.jpg"
$env:NEXT_PUBLIC_SUPPORT_ALIPAY_QR_URL = "https://ai.pricememo.cn/support/alipay.jpg"
# 可选：替换为真实 ID 后启用 GA4 页面浏览和 AI 引荐事件；不启用时保持为空。
# $env:NEXT_PUBLIC_GA_MEASUREMENT_ID = "G-XXXXXXXXXX"

# 百度文件验证材料不进入 Git；每次发布都必须从本机单独上传。
$BaiduVerificationFile = Join-Path (Get-Location) "seo\baidu_verify_codeva-27l7NEdkV0.html"
if (-not (Test-Path -LiteralPath $BaiduVerificationFile -PathType Leaf)) {
  throw "Missing Baidu verification file: $BaiduVerificationFile"
}
$BaiduVerificationName = Split-Path -Leaf $BaiduVerificationFile
$BaiduVerificationHash = (Get-FileHash -LiteralPath $BaiduVerificationFile -Algorithm SHA256).Hash
Write-Output "Baidu verification file: $BaiduVerificationName ($BaiduVerificationHash)"

# Next.js bakes rewrites() into routes-manifest.json at build time, so the
# internal API base must be set here. The web container reaches the API as
# `api:8000` on the compose network; without this the fallback would point at
# the web container itself and /api/* proxying would fail.
$env:INTERNAL_API_BASE_URL = "http://api:8000"
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
scp $BaiduVerificationFile "pricememo-prod:/tmp/$BaiduVerificationName"
scp "C:\Users\59908\Pictures\wechat.jpg" "pricememo-prod:/tmp/wechat.jpg"
scp "C:\Users\59908\Pictures\alipay.jpg" "pricememo-prod:/tmp/alipay.jpg"
```

## 4. Staging 校验、构建和切换

在独立 staging 目录校验 SHA-256、解包、复制生产 `.env`，运行 `production_preflight.py` 和 Compose 配置检查。全部通过后才覆盖运行目录。

```text
1. sha256sum -c 检查两个上传包
2. 解压源码到 /opt/ai-price-radar-staging-$Stamp
3. 解压 .next/standalone 和 .next/static
4. 将 `/tmp/baidu_verify_codeva-27l7NEdkV0.html` 安装到 `/opt/ai-price-radar-staging-$Stamp/apps/web/public/baidu_verify_codeva-27l7NEdkV0.html`，权限 `644`；确认其 SHA-256 与本机 `$BaiduVerificationHash` 一致。该文件必须位于 Web 镜像的 `public` 根目录，不能放到 `support/` 或只留在源码包外
5. 从当前运行目录复制 `.env`；确认 `DETECTOR_WORKER_KEY` 至少 32 字节，且不同于 Admin/Intake Worker Key；`SESSION_SECRET_KEY` 与 `BOT_SECRET_ENCRYPTION_KEY` 各自独立且至少 32 字节（v3.7.92 起强制，缺省会话密钥等于公开可伪造登录态）；`API_DOCS_ENABLED=false`
6. 如果启用搜索引擎通知或站点验证：将 `INDEXNOW_KEY`、`BING_SITE_VERIFICATION`、`BAIDU_SITE_VERIFICATION` 写入生产 `.env`；`BING_WEBMASTER_API_KEY` 和 `BAIDU_PUSH_TOKEN` 只放在执行提交脚本的本机或 CI，不写入 Web 容器。未配置 `INDEXNOW_KEY` 时 `/indexnow-key.txt` 应保持不可用
7. `docker network create pricememo_frontend`（已存在则忽略报错）；确认 `/opt/ai-price-radar-v3/apps/web/public/data` 存在且属主为 `10001:10001`（importer 镜像以该非 root uid 写入公开快照）
8. python3 scripts/production_preflight.py —— 这是硬门禁：退出码非 0 必须中止部署，不得带病覆盖运行目录
9. docker compose ... config -q；确认 `source-detector` 没有数据库凭据、默认网络或 Docker socket
10. 覆盖 /opt/ai-price-radar-v3，但保留 `.env`、`data/`、`backups/`
11. 创建 `/opt/ai-price-radar-v3/data/support`，将两个二维码安装为 `wechat.jpg` 和 `alipay.jpg`，目录权限设为 `755`、文件权限设为 `644`

百度验证文件的 staging 安装示例（在远端 Linux staging 主机执行；文件名以百度后台当前下载的文件为准）：

```bash
# 将 STAMP 替换为本次部署记录中的时间戳。
STAGING="/opt/ai-price-radar-staging-STAMP"
BAIDU_FILE="baidu_verify_codeva-27l7NEdkV0.html"
install -D -m 0644 "/tmp/$BAIDU_FILE" "$STAGING/apps/web/public/$BAIDU_FILE"
test "$(stat -c '%s' "/tmp/$BAIDU_FILE")" = "$(stat -c '%s' "$STAGING/apps/web/public/$BAIDU_FILE")"
sha256sum "$STAGING/apps/web/public/$BAIDU_FILE"
```

该文件是生产部署材料，不属于 Git release；不要执行 `git add seo/`，也不要把它放进 `git archive`。如果百度后台生成了新的文件名或内容，先替换本机 `seo/` 下的文件，再同步修改本节和第 3 步中的文件名。
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

# v10 统一来源发现表：创建 source_discovery_runs 与 source_candidates；
# 必须先在生产 API 切换前在临时 PostgreSQL 16 演练两次，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_source_discovery_v10.py

# 16688 平台来源枚举迁移：允许 16688 店铺申请、发现候选和快照发布；
# 必须在 v10 之后、切换包含 16688 支持的 API / Worker / 发布器前执行，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_source_platform_16688_v11.py

# 16688 库存状态订正 (v12)；把 16688 平台 offer 与 offer_history 中
# stock_status='unknown' 且原始抓取数据显示有货的记录订正为 in_stock，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_16688_stock_status_v12.py

# 用户账号体系与机器人绑定表结构迁移 (v13)；创建 users, user_sessions, auth_codes, user_bot_bindings，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_user_auth_and_bot_v13.py

# 用户价格订阅与通知表结构迁移 (v14)；创建 user_product_subscriptions，扩展 user_bot_bindings，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_user_subscriptions_v14.py

# Claude 商品细分迁移 (v15)；确保 claude-pro-20x 与 claude-team 商品存在，
# 并把 claude-pro 下的团队/20x offer 重新分类，重复执行安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_claude_subdivision_v15.py

# 店铺优惠券与营销口令结构迁移 (v16)；创建 shop_coupons 与 coupon_campaigns，幂等安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_shop_coupons_v16.py

# 商品外链点击与访问统计表结构迁移 (v17)；offers 增加 click_count，创建 offer_clicks，幂等安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_offer_clicks_v17.py

# 优惠券活动关联迁移 (v18)；shop_coupons 增加 campaign_id 与相关索引，依赖 v16 已创建的表，幂等安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_shop_coupon_campaign_v18.py

# 优惠券店铺绑定迁移 (v19)；shop_coupons / coupon_campaigns 增加店铺绑定字段与索引，幂等安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_coupon_shop_binding_v19.py

# 用户密码字段迁移 (v20)；users 增加 password_hash 字段以支持密码登录，幂等安全
docker run --rm \
  --network ai-price-radar_default \
  --env-file .env \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  ai-price-radar-api \
  python scripts/migrate_user_password_v20.py

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
[ ] 新收录申请按 submitted → detecting → pending_review 流转；批准的 Dujiao/Merchant/WooCommerce/Schema.org/16688 来源只有 public_offer_count > 0 才为 published
[ ] `DISCOVERY_WORKER_KEY` 已配置且与 Admin/Intake/Detector Key 不同；crawler 的 `discover-sources` 与 source-detector 候选领取均已接线
[ ] 首次发现运行产生 source_discovery_runs 记录；合格候选经 claim/qualify/result 进入 source_intakes（origin=discovery）
[ ] Schema.org 候选默认停留在 pending_review，未被自动批准（除非显式开启 DISCOVERY_SCHEMA_AUTO_APPROVE）
[ ] 已 published 且仍启用的 Dujiao/Merchant/WooCommerce/Schema.org/16688 来源在连续两次完整刷新中都存在；disabled 来源在下一快照移除
[ ] 首页、报价目录和一个商品详情页可正常访问
[ ] `https://ai.pricememo.cn/baidu_verify_codeva-27l7NEdkV0.html` 返回 200，响应体与百度提供的验证文件完全一致
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

## 6. 可选加固与配套说明

- **systemd 降权**：三个 `ai-price-radar-*.service` 默认以 root 运行（脚本需要 `chown 10001` 和 docker CLI）。如需降权，先一次性配置：

  ```bash
  sudo useradd -r -s /usr/sbin/nologin pricememo
  sudo usermod -aG docker pricememo
  sudo chown -R pricememo:pricememo /opt/ai-price-radar-v3/data /opt/ai-price-radar-v3/apps/web/public/data
  ```

  然后在三个 service 中取消 `User=pricememo` / `Group=pricememo` 注释并 `systemctl daemon-reload`。降权后 `refresh_remote.sh` 会自动跳过 `chown`（仅 root 可执行），目录属主必须预先配置好。注意 docker 组成员实际上等同 root 权限，降权的意义在于 unit 内脚本逻辑不再直接以 root 身份运行。
- **备份保留期**：`scripts/backup_postgres.sh` 默认保留最近 14 份备份，可用 `BACKUP_KEEP_COUNT` 覆盖（0 为禁用清理）。
- **品牌与兼容性豁免**：项目已更名 "AI Price Memory"，但 Atom feed 的 `urn:ai-price-radar` ID、`/.well-known/price-radar.json`、localStorage 键前缀 `apr:`/`ai-price-radar:*` 等对外契约与用户数据键有意保留旧名，避免破坏外部 Agent 与已有浏览器数据；不要在收口文案时"顺手"改掉这些标识符。
- **完整门禁脚本**：第 1 节的手工检查也可以用 `scripts/validate_release.sh` 一次性执行（api/pipeline/detector/scripts 四个测试套件 + 版本一致性 + Web 构建，需本机 bash 环境）。

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

v3.7 回滚补充：应用回滚不删除 v10 表（`source_discovery_runs` / `source_candidates`），旧版本代码不读取新表，不应受影响；不回滚 PostgreSQL。发现系统异常时可单独暂停 `ai-price-radar-discover.timer` 或停止新 Discovery Worker，当前公开快照不会因发现系统失败而变化。
