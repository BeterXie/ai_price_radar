# Release Notes v3.7.55

## 变更摘要

- **新增前沿技术实测博文（`/skills/codex-context-management-experimental-mode`）**：
  - 核实并收录 2026 年 9 月 OpenAI Codex 隐藏特性爆料：在 `~/.codex/config.toml` 中配置 `[features.context_management] experimental_mode = true`。
  - 全面拆解该实验性模式如何通过“跨窗口持久笔记 + 历史语义检索”取代旧版暴力 Compaction 压缩，大幅降低长对话 Token 消耗、杜绝行号丢失与后半程降智。
  - 详细提供 Windows / macOS 跨平台配置文件位置与一键配置指令，支持在 `/skills` 列表中按「技巧博文」快速查阅并复制配置。
  - 详情页挂载 ChatGPT Plus 与 Codex 订阅比价，提供一站式决策参考。

## 验证

- 后端 332 项自动化测试全部通过。
- 前端 65 个页面与静态路由生成完毕，无类型错误与 localhost 泄漏。
