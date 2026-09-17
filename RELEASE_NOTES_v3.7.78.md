# Release Notes - v3.7.78

## 概述

v3.7.78 实现了两大重点功能：
1. **Claude 细分规格矩阵与精准同质可比体系**：支持将原本单一的 Claude Pro 拆分为 `Claude Pro (5x)`、`Claude Pro 20x`（高配满血号）和 `Claude Team`（团队车位与席位），避免不同规格商品报价混杂。
2. **机器人品牌全系列最低报价聚合卡片**：在 QQ / Telegram 机器人中发送 `claude`、`openai`、`gemini`、`grok` 等品牌词时，一键返回该品牌所有细分规格的最低在售报价与库存；输入具体型号时依旧保留 Top 5 深度比价。

## 变更内容

- **分类器增强**：
  - `apps/api/app/services/classifier.py` 和 `pipeline/common.py` 全面支持 Claude 20x、Team、5x 的智能识别。
- **数据迁移支持**：
  - 新增 `scripts/migrate_claude_subdivision_v15.py`，支持线上数据库无损幂等重分类存量报价。
- **机器人指令路由升级**：
  - `extensions/bots/chat_commands.py` 增加 `query_brand_lowest_prices`，支持品牌全系列聚合卡片生成；
  - 优化单品与品牌指令路由。
- **前端目录与 SEO 同步**：
  - `apps/web/lib/catalog.ts` 和 `apps/web/lib/product-seo.ts` 补充 Claude Pro 20x 与 Team 规格。
