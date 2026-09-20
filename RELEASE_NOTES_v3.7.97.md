# Release Notes - v3.7.97

**发布日期**: 2026-09-21  
**发布版本**: 3.7.97

## 变更概述

修复生产 Web standalone 镜像构建时 `.dockerignore` 排除 `.next` 导致构建上下文缺少已生成产物的问题。

## 部署说明

- 生产 Web 镜像只接收 `.next/standalone` 与 `.next/static`，其余 `.next` 缓存仍被忽略。
- 本版本沿用 v3.7.96 的 API、Pipeline、source-detector 与 notification-worker 改动；无新增独立数据库迁移脚本。
- 继续按 `docs/QUICK_DEPLOY.md` 完成 staging 预检、备份、镜像切换和发布验收。
