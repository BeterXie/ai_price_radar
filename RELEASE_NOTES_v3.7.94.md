# Release Notes - v3.7.94

**发布日期**: 2026-09-19  
**发布版本**: 3.7.94

---

## 变更概述

v3.7.94 重点扩充了链动小铺（LDXP / wzyp.cn）店铺与 AI 商品品类的收录能力，解决了爬虫关键词过窄导致非 GPT 商品（如 SuperGrok、Codex接码、Team 车位等）被丢弃的问题；并在分类器中增加了别名容错和接码服务支持；同时正式录入 Ai2You智友社 与 吾爱API的小店 两个优质店铺。

---

## 核心变更

### 1. 爬虫抓取关键词扩充与品牌保障
- **关键词扩充**: crawler/ldxp/ldxp_gpt_crawler.py 默认抓取关键词 DEFAULT_KEYWORDS 由 ["gpt", "chatgpt"] 扩充至全量支持品类（grok, supergrok, codex, claude, gemini, cursor, 	eam, 接码 等）；
- **品牌回退机制**: crawler/ldxp/ldxp_crawler/browser_scanner.py 中增加回退保障，只要商品命中已定义的目标 AI 品牌，自动提取匹配品牌为 hit，防止合法商品因关键词过滤被丢弃。

### 2. 分类器别名容错与服务支持
- **Grok 系列增强**: 支持商家缩写与漏字（如 super gro）识别，支持 heavy 高配识别，准确定位至 grok-super；
- **手机接码服务扩展**: 支持 接收验证码、自助接收验证码，将 Codex 美区卡自助接收验证码 稳定归入 chatgpt-access-service；
- **OpenAI Team 团队席位**: 强化 OpenAI / ChatGPT Team 车位归入 chatgpt-k12（交付形式 	eam_seat）。

### 3. 店铺录入
- 将 https://wzyp.cn/shop/282D9KDL（Ai2You智友社）与 https://wzyp.cn/shop/ODI7TT6O（吾爱API的小店）添加至种子库及 source_intakes。

---

## 升级与迁移说明

- 本次发布无数据库表结构变更，无迁移脚本；
- 遵循 docs/QUICK_DEPLOY.md 生产标准部署：
  - 重建 pi、web、crawler 容器。
