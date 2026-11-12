# v3.9.66

链动小铺采集器补充 Muse 品牌识别，修复商品已抓取但被过滤、店铺申请误报“没有商品”的问题。Muse 账号和邀请助力进入现有分类与快照发布流程；同分类下的 TG Premium / Telegram Premium / 电报会员不会因分类名称被当作 Muse 商品。

新增回归覆盖混合商品店铺、价格与库存保留、旧关键词配置以及收录验证结果。没有数据库迁移。按 `docs/QUICK_DEPLOY.md` 与 `docs/MULTI_BRAND_DEPLOY.md` 发布，并重建 crawler；完成一次完整目录发布后重试此前受影响的收录申请。
