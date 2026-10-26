# v3.9.27 套餐分类与中转站缓存采集

本次合并两个会话的改动：账号套餐修正及 MUSE / JEV 接入，以及已提交但暂停发布的 `515a3e2`（AllTokens 稀疏缓存用量兼容）。生产基线为 v3.9.25。

## 用户可见变化

- 套餐筛选按已核验的官网名称展示，旧版倍率、商家标签、API 与等级未注明商品单独列出。
- Business / Team 席位不再进入 OpenAI Pro；Perplexity 不再因包含 GPT / Claude 模型或美元价格而误分到 OpenAI。
- MUSE / JEV 接入链动小铺和 16688 的发现、同步与前台品牌筛选。未核验的套餐等级不作推断。
- 明确写 15 天的商品显示对应的期限与质保。
- AllTokens 对话接口缺少缓存字段时，使用同一密钥的用量增量核对单次探活；无法核对时继续保持未知，原有近 24 小时统计口径不变。

## 发布要求

遵循 `docs/QUICK_DEPLOY.md`。无数据库结构迁移，不执行历史迁移脚本。

1. 同一提交通过 CI，发布 Tag，并验证本地工作区干净。
2. 暂停三个定时器，等待刷新锁，备份一次 PostgreSQL，保存旧源码与 API / Web / Importer / Crawler 回滚镜像。
3. 上传同一 Tag 的源码与生产 Web standalone；完成 staging preflight 和 Compose 检查。
4. 重建 API、Web、Importer、Crawler。API 切换前运行 `scripts/reclassify_account_offers.py --dry-run`，审查分类迁移汇总，再执行 `--apply`。人工锁定和隐藏状态保留。
5. 执行一次完整多来源刷新并确认 `published=true`、`failed=0`；核对真实 MUSE、Business / Team、Pro 商品及新品牌入口。
6. 验收版本、容器健康、来源隔离、验证文件、价格与日志，恢复三个定时器。

套餐研究与本地演练记录见 `ACCOUNT_PLANS_AND_RELAY_MONITORING.md`；缓存采集实现、真实核验和代码评审记录见 `REVIEW_v3.9.26.md`。
