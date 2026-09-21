# Release Notes - v3.7.99

**发布日期**: 2026-09-21  
**发布版本**: 3.7.99

## 变更概述

在「技能与实验室」（`/skills`）体系中新增**「模型PK」**（`kind="pk"`）分类，并发布高难度机械与几何空间推理基准——“螃蟹骑带辅助轮三轮车 12s 纯矢量动画”双模型实测及交互竞技场：

1. **新增模型PK专属分类与标签导航** (`kind="pk"`):
   - 顶部导航栏新增 `⚔️ 模型PK` 标签页，支持独立筛选所有双模型对决与横向对比内容。
   - `SkillCard` 与 `SkillDetailView` 适配金色 `Sword` 图标徽章，CMS 管理面板支持 PK 内容管理。
2. **交付 CrabArena 交互式对决竞技场** (`apps/web/components/skills/crab-arena.tsx`):
   - 支持**双列分屏实时同屏运行**与**单视窗精选切换**。
   - 呈现建模维度、转向拟真、肢体绑定、代码量、环境动效与交互增强 6 大维度全景对比表，内置一键复制官方 4 大严苛约束测试 Prompt。
3. **发布 3 份实测内容与自包含动画资源** (`/demos/pk/`):
   - `crab-riding-tricycle-pk`：大模型极客对决：GLM-5.3-Flash vs Gemini 3.8 Flash 螃蟹骑三轮车实测 PK（`crab_arena` 交互竞技场）。
   - `crab-tricycle-glm-5-3-flash`：GLM-5.3-Flash 实测：螃蟹骑三轮车 12s 纯矢量自包含动画（542 行 / 27.8 KB，轻量优雅切线运动学与 LCG 微风花坛）。
   - `crab-tricycle-gemini-38-flash-medium`：Gemini 3.8 Flash (Medium) 实测：螃蟹骑三轮车 3D 动力学与音效工程狂魔（1652 行 / 80.3 KB，3D 轴测投影、阿克曼转向角、Web Audio 双音车铃与脚踏声、独立 SVG 导出）。

## 部署说明

- 本次改动涉及前端静态 Demo 资源发布（`apps/web/public/demos/pk/`）、分类与组件更新，以及 API 种子定义（`apps/api/app/services/seed_skills_data.py`）。
- API 容器启动时会自动通过 `seed_default_community_skills` 将新 PK 内容同步到生产 PostgreSQL 数据库中。
- 按 `docs/QUICK_DEPLOY.md` 规范重新构建并部署 `api` 与 `web` 容器，无新增数据库结构迁移脚本。
