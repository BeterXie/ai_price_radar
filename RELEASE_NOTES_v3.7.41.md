# AI Price Radar v3.7.41 Release Notes

**Release Date**: 2026-09-05  
**Tag**: `v3.7.41`

---

## Highlights

### 1. 精准修正 Free 账号与辅助工具被错误归类为 ChatGPT Plus 的问题（Classification Accuracy Fix）
- **根因分析**：
  - 历史导入的部分独立店铺商品（如 `#12414`, `#12415` `G Free-账密 RT/AT-长效outlook-适合各类业务(可网页反代，除Codex)` 单价 ¥0.30），标题中的“除Codex”被错误当作品牌词 Codex 命中，且其带有的“反代专用”标记在旧逻辑中强行回退到了 `chatgpt-plus`。
  - 另外部分提链/提炼 CDK 工具（如“菲区提炼CDK 次卡 直卡支付链接 卡头开通plus必备” 单价 ¥1.50）因标题含有“开通plus”被误划入 Plus。
- **分类器深度优化**：
  1. **排除词清洗**：引入 `_strip_exclusions`，在匹配品牌和规格前干净剥离 `除Codex`、`不可codex`、`除Plus` 等否定搭配词，杜绝“除Codex”被视作 Codex 品牌的 Bug。
  2. **Free 账号词根全量扩充**：扩充 `CHATGPT_FREE_MARKERS`，新增识别 `g free`, `g-free`, `gfree`, `codex free`, `outlook/icloud/gmail free`, `free账密`, `free成品`, `free底号`, `可升级plus`, `开plus专用`, `好底号`, `未绑卡` 等普号底号，精准归类为 `chatgpt-account`（ChatGPT 普号）。
  3. **反代专用不再覆盖 Free 普号**：调整反代与 Free 识别优先级，即使带反代/Session Token，只要属于 Free 普号底号，一律归入 `chatgpt-account`。
  4. **提链与接码卡密划入辅助服务**：扩充 `CHATGPT_SERVICE_MARKERS`，增加 `提炼`, `代提链`, `直卡支付链接`, `支付链接`, `卡头开通plus必备`, `提炼cdk`, `实卡号码`, `无限接马`，正确归类为 `chatgpt-access-service`（ChatGPT 辅助接码与支付）。
  5. **ChatGPT Plus 价格防线 (< 8.00 元守卫)**：
     - Plus 账号在市面上极少低于 8 元；针对分类为 `chatgpt-plus` 且标价 < 8.00 元的商品增加二级校验：
       - 若含普号/底号/升级词汇，降级纠正为 `chatgpt-account`；
       - 若含提链/支付链接/接码词汇，降级纠正为 `chatgpt-access-service`；
       - 其余超低价商品自动打上 `abnormal_low_price` 风险标签。
  6. **双端引擎同步**：完整同步了 `apps/api/app/services/classifier.py` 与 `pipeline/common.py` 的规则，确保后续采集爬虫写入和 API 动态重算完全一致。

### 2. 线上存量数据与快照全量清洗（Database Migration）
- 生产环境迁移脚本自动重算存量低价 Plus 商品与 Free 账号。
- 触发全量目录快照刷新，前台 ChatGPT Plus 最低价即刻恢复真实行情（>= 8 元），彻底剔除 0.3 元普号与 1.5 元提链工具对 Plus 行情榜的干扰。

---

## Verification
- **Backend Tests**: 257 passed (`python -m pytest tests/`).
- **Pipeline Tests**: 135 passed (`python -m pytest pipeline/tests/test_classifier.py`).
- **Web Tests**: 55 passed (`node --import tsx --test`).
- **TypeScript Check**: Clean pass with zero errors (`tsc --noEmit`).
