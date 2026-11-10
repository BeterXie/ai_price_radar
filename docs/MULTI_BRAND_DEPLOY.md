# 多品牌发布

本文件补充 QUICK_DEPLOY.md，不替代其干净工作区、Tag、CI、备份、迁移演练、
staging preflight 和回滚要求。v26 有数据库结构变更，部署后必须完成一次完整多来源发布。

| 构建 SITE_ID | 对外域名 | Caddy 上游 |
| --- | --- | --- |
| pricememo | ai.pricememo.cn、pricememo.cn | ai-radar-web:3000 |
| aiprice | aiprice.si | ai-radar-aiprice:3000 |
| aisi | aisi.plus | ai-radar-aisi:3000 |
| pricein | pricein.cc | ai-radar-pricein:3000 |
| openprice | openprice.in | ai-radar-openprice:3000 |

主站 canonical 始终为 https://ai.pricememo.cn；根域名直接展示同一套页面。
不要给主站构建设置 NEXT_PUBLIC_SITE_URL=https://pricememo.cn。
新站 canonical 固定为自身域名，不信任请求 Host。浏览器 API 使用同域路径；
所有前端都反向代理到同一个 API，数据库、快照发布器、定时采集和报价统计只有一份。
账户共用账号资料，但不同域名有独立 Cookie，需要分别登录。

## 构建与迁移

1. 按标准 runbook 完成测试与 CI，发布同提交 Tag。
2. 停止本地 next dev。从干净 Tag 工作区执行：

       pwsh -File scripts\build_brand_frontends.ps1 -ReleaseTag vX.Y.Z

   脚本为五站顺序构建并分别打包 standalone、static、public 和 Dockerfile.prebuilt，
   输出各包 SHA-256。二维码和百度文件按标准 runbook 单独安装到主站 staging。
3. 上传源码包及五个前端包，校验 SHA-256。在各自独立 staging 目录解包；
   同一个 .next 目录只能对应一个站点构建，不能混用。
4. 临时 PostgreSQL 16 使用数据库 brand_migration_test，设置
   SITE_TEST_DATABASE_URL 后运行 apps/api/tests/test_sites_postgres.py。
   该测试要求空数据库，会创建旧商品与中转站最小结构，然后连续执行迁移两次，
   核对原商品未变、时间字段带时区且未复制文章。CI 的 API job 也执行此检查。
5. 通过标准 preflight 后构建 API 和 importer。在切换 API 前，以新 API 镜像运行
   python scripts/migrate_multi_brand_v26.py。v26 只增加 site_articles、
   site_relays 和 site_ads，不更改现有报价、商品、账号或快照。
6. 用各站 staging 的 Dockerfile.prebuilt 构建镜像
   ai-price-radar-web-{site}:vX.Y.Z；主站按原有镜像名构建。
   四个新站 Compose 使用 BRAND_RELEASE_TAG=vX.Y.Z，不得使用不明来源的 latest。
7. 使用原有两个 Compose 文件切换 API、主站和 importer。再增加
   -f docker-compose.brands.yml 启动 web-aiprice web-aisi web-pricein web-openprice。
   四站只读挂载同一份 apps/web/public/data，不启动额外采集进程。

## 入口和 DNS

生产 Caddy 是独立容器。先通过 docker inspect 核对配置挂载，保存当前配置，
将 deploy/brands.Caddyfile 的内容纳入实际配置；不要覆盖该容器中其他应用的站点。
把主站块的域名改为 ai.pricememo.cn, pricememo.cn，保留原有访问控制。
caddy validate 通过后再 reload，失败则保留旧配置。

四个新站在 Caddy 层禁止 /admin 和管理/内部 API；统一后台仍在原主站。
新站首次上线前中转站目录和文章默认为空，需运营者独立选择与发布。

DNS 指向经核验可服务这些域名的源站，Cloudflare 使用完整（严格）TLS；
先确认源站证书和 Host 路由，再启用代理。保留现有 MX/TXT/邮箱记录。
www 不在本次要求内；不要添加没有 TLS 与路由配置的别名。

每站验收：HTTPS 首页、商品目录、商品详情、文章空状态或本站文章、中转站；
检查 canonical、JSON-LD、favicon、robots 与 sitemap 域名。主站与根域名应返回
同版本且 canonical 都指向 ai.pricememo.cn。各站商品 snapshot_id 和同一报价金额一致。
使用邮箱登录时 Cookie 应属于当前访问域名，后台入口只允许主站。

## 日常内容和搜索引擎

原后台 → 品牌站点 → 当前站点，可分别管理文章草稿/预览/发布/撤回、
中转站收录与介绍、广告、公告、搜索验证码和统计 ID。
新站不复制原站 guides/skills；原路径转到本站文章目录。
主站旧教程与社区内容保留原管理方式。

Google、Bing、百度均需为每个域名单独建立站点属性、完成所有权验证并提交
https://该域名/sitemap.xml。后台填写的是 HTML meta 的验证码内容，不是整个标签。
需要 DNS TXT 验证的平台应按平台当前给出的值添加记录，不能自造验证码。
代码提供验证与 sitemap 不代表平台账号已验证，也不代表一定收录或获得排名。
不要将同一篇文章换标题后批量复制到四站。

新站 GA4/百度统计默认不加载。为各站分别配置统计 ID；
主站现有环境变量验证码在后台字段留空时继续有效。
IndexNow 推送及旧的搜索提交脚本仍按其传入域名工作，不能把主站 key 自动复制到新站。

## 回滚

按标准 runbook 回滚主站 API/Web/importer，不删除 v26 新表。
品牌镜像按 Tag 保留；后续回滚修改 BRAND_RELEASE_TAG 后仅重建四个前端容器。
首次上线失败则停止新增前端、恢复 Caddy 备份和本次新增 DNS 记录，
不要回滚数据库或覆盖其他站点配置。
