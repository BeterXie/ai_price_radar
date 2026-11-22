# v3.9.97

新增邮箱、接码 / 验证、虚拟卡、礼品卡、社媒账号、Apple ID 和 VPS 分类，支持公开采集、归类、快照、主站及四个品牌站筛选。原 OpenAI、MUSE、JEV 验证商品统一归入验证分类，保持原商品 ID 和历史；现有 X 普通账号继续使用独立分类。

保留现有套餐识别、短名账号识别和人工审核决定，避免描述里的邮箱、卡片和使用场景改变主商品。虚拟卡、礼品卡、VPS 使用各自的交付标签。金额保留商家原始单位，未做面额与服务器配置归一化。

无数据库结构迁移。按 QUICK_DEPLOY.md、MULTI_BRAND_DEPLOY.md 和 COLLECTOR_DEPLOY.md 发布：更新 API、五个 Web、importer、source-detector、主站 crawler 和 Oracle collector；两端保持 COLLECTOR_RELEASE 一致，保留 COLLECTOR_LDXP_ENABLED=false。

上线需重扫 LDXP 来源并完成 Oracle HTTP 来源的完整发布，核对分类和快照一致后恢复调度。历史重分类使用现有入口并保留人工锁定与隐藏状态。详见 docs/AUXILIARY_CATALOG.md。
