# Release Notes - v3.9.15

发布日期：2026-10-24

- 按品牌拆分 OpenAI、Claude、Gemini、Cursor、Grok 的账号套餐；未注明等级、历史名称及普通账号独立归类，采集与后台重分类共用规则。
- 搜索采用多词交集并保留品牌、来源、库存、周期等筛选；详情、分组展开及分页保持搜索范围。
- 前台新增中转站站长申请，使用现有后台审核上线；Base URL、检测协议、模型和加密密钥由后台管理，申请说明和凭据不公开。
- 支持三种协议的短文本生成探活，展示近 24 小时成功率、有效样本及 P95。配置诊断独立计数，数据库原子领取和配置快照避免同一版本重复探测。
- 修复评审发现的套餐与交付混淆、模型名误判、免费账号保护、来源筛选丢失、不可解密旧密钥替换及配置变更时的探测并发问题；补齐来源检测镜像的共享分类依赖。
- 将 Next.js 升级至 16.4.3，修复发布审计发现的远程代码执行及拒绝服务漏洞。

部署必须先在临时 PostgreSQL 16 执行两次 `scripts/migrate_relay_monitoring_v22.py`，确认保留旧中转站且幂等。生产切换 API 前使用新 API 镜像执行同一迁移。新增申请字段、检测配置字段和 `relay_probe_results`，旧中转站默认已审核但不开启监测；不重建 PostgreSQL。

按 `docs/QUICK_DEPLOY.md` 发布，重建 `api`、`web`、`source-detector`、`importer`、`crawler`。需要当前版本执行一次完整多来源刷新并确认 `failed=0`、`published=true`，更新已有报价分类并保留人工覆盖。保留既有 `BOT_SECRET_ENCRYPTION_KEY`，不轮换加密材料。

探活按所配置的模型和密钥采样，不能证明所有模型或全站 SLA；未提供商家真实凭据前不宣称完成实际接口兼容性验证。PriceAI 源码参考范围、许可证边界及实现差异见 `docs/ACCOUNT_PLANS_AND_RELAY_MONITORING.md`。
