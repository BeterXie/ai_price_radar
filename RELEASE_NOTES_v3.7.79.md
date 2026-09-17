# Release Notes - v3.7.79

## 机器人查价与公共前台大盘规则严格对齐 (v3.7.79)

### 变更概述
在接收到用户关于“机器人的答复应该遵守我们项目后台的规则限制，只返回可在前台分类可以查看到的，保持规则一致”的反馈后，本版本对机器人指令模块进行了重构与严格对齐：
- **统一公共报价检索标准**：机器人各查价指令（品牌聚合 `query_brand_lowest_prices`、单品对比 `query_lowest_price`、大盘行情 `query_market_overview`、降价榜单 `query_recent_drops`、个人订阅 `query_user_subscriptions`）全面弃用过去的裸 SQL 查询，统一接入底层 `_base_public_offer_query`；
- **全方位过滤垃圾与被封禁报价**：
  - 自动剔除 `approved == False`（未审核）、`hidden_reason != ""`（如管理员封禁、违规下架）、`active == False` 以及过期失效的报价；
  - 严格限制 `Shop.is_visible == True` 且过滤已停用的抓取平台；
  - 集成前端相同的 `_is_trusted_offer` 中位数风控规则，过滤偏离市场行情的虚假或非同质低价诱饵；
- **库存策略优化**：优先展示库存量 $\ge 2$ 的稳定现货商户；若全网仅剩单件现货则自动降级兜底展示，绝不错过真实上架货源。

### 数据库迁移说明
本版本为纯业务查询逻辑重构与风控对齐，无数据库 DDL 结构变动，无需执行迁移脚本。
