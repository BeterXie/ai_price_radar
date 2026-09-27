# Release Notes - v3.9.5

**发布日期**: 2026-09-27
**发布版本**: 3.9.5

## 变更概述

- 将 Meta Muse (muse.ai) 注册激活与绑卡避坑指南迁移收录至 **「AI 技能与实验室」** (`/skills/meta-muse-registration-guide`)，归类于“✍️ 技巧与博文”专区。
- 提供一键复制 Gemini Spark 远端浏览器操作指令、官方直达通道与专属邀请码 RJHEX9（立得 10 亿 Token）。
- 从基础教程分类中撤除该条目，保持通用教程中心聚焦标准商品核验。

## 部署说明

- 无数据库结构变更。
- API 启动时自动通过 `seed_default_community_skills` 同步最新的技能条目至 PostgreSQL。
- 按 `docs/QUICK_DEPLOY.md` 流程发布，重建 `api`、`web` 和 `importer` 服务。
