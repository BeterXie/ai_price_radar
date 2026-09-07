# Release Notes v3.7.53

## 变更摘要

- **社区技能库与模型降智检测实验室（/skills, /skills/[slug]）**：
  - 新增前台公开「技能与实验室」板块，支持按「全部、降智评测、实用技能、技巧博文」多维度筛选与关键词搜索。
  - 内置沙箱互动竞技场（`PelicanArena`），对比 6 套真实评测案例（GPT-6-Astra 满血版 vs 降智版、GPT-5.6 调教版 vs 网页版、Gemini 3.8 Flash、猪八戒骑车），支持一键切换预览与提示词复制。
  - 首批引入 11 个优质 Skill/Benchmark，均溯源至 GitHub 官方仓库与原作者（包含 `taste-skill`, `victor-design`, `awesome-design-ui`, `agent-browser`, `open-code-review`, `storage-analyzer`, `grilling`, `domain-modeling`, `agently-mail` 等）。
  - 详情页深度联动核心比价引擎，根据技能适用的目标模型（ChatGPT Plus、Claude Pro、Codex 等）动态挂载实时比价购买卡片，实现高意向引流转化。
- **后台 CMS 技能管理面板（/admin）**：
  - 支持对技能、降智评测与社区博文进行完整的发布、编辑、置顶、删除与显隐开关控制，支持后续持续输出。
  - 支持查看阅读量（`view_count`）与复制量（`copy_count`）。
- **版本规范与基础设施**：
  - 统一更新项目版本为 `3.7.53`。
  - 动态站点地图 `sitemap.ts` 支持技能与评测详情页 SEO 索引。

## 验证

- `apps/api/tests/test_community_skills.py` 覆盖公开列表过滤、详情、浏览计数、复制计数及管理员 CRUD，后端 332 项测试全部通过。
- `apps/web` 生产构建成功，65 个页面与静态路由生成完毕，无类型错误。
