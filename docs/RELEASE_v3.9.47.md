# v3.9.47 — X 基础账号与服务套餐收录

新增 X 基础账号分类，用于普通 X / Twitter 账号与成品号，保留 Premium 会员和统一订阅的独立分类。其他社交账号仍按现有规则过滤。

来源检测与采集支持 Schema.org Service 的具名报价，包括直接 Offer 和一层 OfferCatalog。按各套餐自己的名称、价格、币种和库存分别收录，沿用稳定报价标识及原始数据。gpt-plus.ai 首页的 Plus、Pro 100 和 Pro 200 可通过标准审核与完整目录发布流程进入前台；其人民币金额是商家公示参考价，实际支付以商家结算页为准。

验证包括真实来源只读采集、套餐分类与身份稳定性、无效报价过滤、X 与其他社交账号边界，以及 API、Pipeline、Detector 和 Web 测试。

无需数据库结构迁移。严格按 QUICK_DEPLOY.md 从 CI 通过的发布 Tag 部署，重建 API、Web、source-detector 和 importer。在标准收录工作流处理申请后执行一次完整多来源发布，确认 failed=0、published=true 与两家店铺实际公开报价，再恢复三个定时器。
