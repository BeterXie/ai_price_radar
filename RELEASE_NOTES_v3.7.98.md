# Release Notes - v3.7.98

**发布日期**: 2026-09-21  
**发布版本**: 3.7.98

## 变更概述

在「✍️ 技巧与博文」（`kind="article"`）分类下发布 3 篇深度技术与前沿实践博文，并完善自动种子灌入与搜索引擎收录支持：

1. **Jev 1.13 深度解读** (`jev-1-13-system-one-model`): 剖析 TypeSafe AI 推出的 System One Model，聚焦结构化确定性决策、\$0.042/1M 输入低价与免费输出，以及与通用大模型协同的双引擎架构。
2. **多模型分工实战指南** (`multi-model-workflow-routing-2026`): 详解生产级四层漏斗架构（快速初筛 → 主力生成 → 专家攻坚 → 规则验证），基于真实数据案例实现大幅降本。
3. **GLM-5.3 Infra Agent 与自我改进分析** (`glm-5-3-infra-agent-recursive-self-improvement`): 拆解智谱 10 万卡集群推理底层优化内幕，辨析递归自我改进真相，提炼细粒度工程反馈闭环方法论。

## 部署说明

- 本次改动涉及 API 种子定义（`apps/api/app/services/seed_skills_data.py`）与版本升级。
- API 容器启动时会自动通过 `seed_default_community_skills` 将新文章同步到生产 PostgreSQL 数据库中。
- 按 `docs/QUICK_DEPLOY.md` 规范重建 `api` 与 `web` 容器，无新增数据库结构迁移脚本。
