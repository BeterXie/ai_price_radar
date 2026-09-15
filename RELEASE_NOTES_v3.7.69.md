# AI Price Radar v3.7.69 — Admin Tab Navigation, Operational Notices & UI Polish

## 概述

本版本重点增强了管理后台的操作效率与前台运营灵活性：实现后台 6 大核心模块的吸顶 Tab 化直达与无损状态切换；新增页面顶部横条公告（Site Notice）与加入交流群引导弹窗（Community Notice）的后台可视化配置与实时预览；同时修复了 Tailwind CSS v4 层级引发的加群按钮黑底黑字及文章编辑保存按钮隐形缺陷。

## 变更明细

1. **后台功能模块 Tab 化导航 (Admin Tab Navigation)**:
   - 增加顶部吸顶 Tab 栏，划分 6 大管理模块：`⚙️ 运营与配置`、`🏪 店铺审核`（含待初审 Badge）、`📝 社区玩法与文章`、`🌐 公网来源发现`、`⚠️ 纠错与反馈`（含待处理 Badge）、`🏷️ 报价与分类`（含未分类 Badge）。
   - 采用纯容器显示切换，切换 0 延迟且不丢失表单输入、滚动位置或筛选状态；支持 URL `?tab=xxx` 同步与 deep link。

2. **页面顶部横条公告（Site Notice）后台可视化配置**:
   - 后台可配置开关、徽标标签（Badge）、主标题、详细正文、按钮文案及目标跳转链接。
   - 配备实时前台效果预览框与一键快捷开关，配置保存后前台刷新即可生效，并兼顾本地会话叉号关闭记录。

3. **加入 AI 比价交流群引导（Community Notice）后台配置化**:
   - 后台可配置弹窗开关、主标题、说明文案、QQ群号、一键加群链接及按钮文案，配备实时弹窗预览框。
   - 前台根据配置动态渲染，并可通过后台随时开启/停用。

4. **UI 缺陷修复 (UI Bug Fixes)**:
   - 修复 Tailwind CSS v4 下全局未分层 `a { color: inherit; }` 覆盖 utility 类导致链接按钮出现黑底黑字的隐形问题，移入 `@layer base` 并加固 `!text-white`。
   - 修复文章编辑弹窗底部保存发布按钮因全局变量缺失导致的白字透明底隐形问题。

## 生产部署说明

- 本次改动涉及 `apps/api` 与 `apps/web`，不涉及数据库结构变更或迁移。
- 遵循 `docs/QUICK_DEPLOY.md` 标准发布流程重建 `api` 与 `web` 容器。
