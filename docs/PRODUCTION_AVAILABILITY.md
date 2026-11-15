# 可用性修复部署补充

本文件补充 QUICK_DEPLOY.md 和 MULTI_BRAND_DEPLOY.md；不改变 Tag、CI、备份和 staging 门禁。
本次没有数据库迁移。重建 API、importer、五个 Web；验证完整刷新成功后恢复三个采集 timer。

## 数据与缓存

发布器先写不可变完整快照及 v1/catalogs/{id}.json 商品摘要，最后原子更新 latest.json。
Web 每 30 秒检查共享目录的小指针，每个新版本只加载一次摘要；并发请求共用加载。
摘要禁止包含 offers/top_5_offers，最大读取 512 KiB；页面读取失败可沿用上次成功结果 5 分钟，
之后走普通 API。商品统计、排序、币种和更新时间保持原有语义。

新 Web 切换前，用已构建的新 importer 对当前不可变快照生成摘要。该步骤只写公开派生文件，
不修改数据库：在 importer 中调用 export_snapshot.write_catalog_summary，读取共享目录的
latest.json 和其指向的完整快照。随后完整刷新验证后续版本也会持续生成摘要。
保留旧完整快照和最新指针的既有对外用途。

## 网络

pricememo_frontend 的固定地址为：API .2、主站 Web .4、AISI .5、
OpenPrice .6、PriceIn .7、AIPrice .8（均为 172.18.0.x）。
切换前核对网络 CIDR、地址占用；切换后核对每个容器的 IPAMConfig 和实际地址。
五个 Web 使用 extra_hosts 将 api 解析到 .2；构建地址仍为 http://api:8000。

先备份实际挂载的 Caddyfile，再执行：

    python3 scripts/render_production_proxy.py CURRENT_CADDYFILE CANDIDATE_CADDYFILE

该脚本只替换已知 API/Web 上游和公开数据路径，保留其他域名及日志配置。
将候选文件复制进 Caddy 容器临时路径，执行 caddy validate。
验证通过且上游固定地址正确后，更新宿主机挂载文件，再执行 caddy reload。
若配置是单文件 bind mount，更新时保留宿主机原文件 inode；不要以 rename 替换被挂载文件。
失败立即恢复 Caddyfile 备份并 reload，不重启数据库。

公开 data feed 由 API FileResponse 直接流式发送，避免 Next.js 转发完整大文件。

## 资源与旧服务

API 上限 1280 MiB，主站 Web 512 MiB，品牌 Web 各 384 MiB；这些是上限，不是预分配。
爬虫仍限制 800 MiB/1 CPU，importer 600 MiB/1 CPU，降低后台 CPU shares。
后台浏览器启动前要求 available >=1100 MiB，发布前要求 >=900 MiB；不足则记录延期，
等待下一轮调度，不能强杀在线服务。缺失内存指标是错误，不能当作预算足够。
现有全局刷新锁继续约束调度任务；手工全量刷新也必须通过 refresh_remote.sh。

若旧 pricememo App 已停止，确认 MySQL/Redis 没有其他网络消费者、没有活动连接，
并保留最新旧库备份后，可停止这两个旧容器及旧 MySQL 备份 timer；保留卷和配置。
记录容器与 timer 状态，回滚可 docker start 和 systemctl start。
不删除数据库、镜像或备份。当前 PostgreSQL 必须有日常备份 timer。

主机已有 2 GiB Swap。将 vm.swappiness 从 0 调整为 10 前记录原值，并在
/etc/sysctl.d/ 中写入本次配置；观察页面延迟和 swap-in/out。回滚恢复原值及配置文件。
内存告警和后台准入是保护措施，不能代替持续的容量评估。

## 监测与验收

安装 deploy/systemd/ai-price-radar-availability.service 和 .timer，
执行 systemctl daemon-reload 与 enable --now，每分钟检查公网页面、容器、内存和 OOM。
结果写入 data/ops/health.json；异常退出非零并进入 systemd journal。
GitHub Production availability 工作流每 5 分钟从外部检查相同页面，失败进入 Actions 失败记录；
通知是否送达取决于仓库所有者的 GitHub 通知设置，未新增邮件或第三方 Webhook。

增加日常 PostgreSQL 备份 timer，每天按 scripts/backup_postgres.sh 执行，
沿用 14 份备份保留策略。部署期间暂停该 timer，避免与发布前的一次备份重复。

验收：五站同版本、主站/提交页/商品页/业务 API 为 200，API/Web/DB healthy，
摘要与完整快照统计一致且小于 256 KiB，完成一次完整刷新、快照指针推进、全部来源成功。
部署后的日志不得出现新 OOM、内部上游 DNS 超时、超大 Next.js 缓存报错或通知模块缺失。
本次核心测试验证 100 个并发读取只加载一次、版本复用、坏文件降级和过期停止降级。

发布结束记录监测起点；72 小时观察结果应由监测数据支持，不能提前宣称已经完成。
