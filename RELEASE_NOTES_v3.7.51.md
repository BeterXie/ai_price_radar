# Release Notes v3.7.51

## 变更摘要

- 后端管理路由新增 `POST /api/v1/admin/source-candidates/cleanup` 批量清理端点：
  - 支持清理 `no_match`（无 AI 商品）、`validation_failed`（验证失败）、`disabled`（已停用）、`rejected`（已拒绝）等无效候选记录。
  - 强制安全校验，确保已提升/收录候选（`promoted`）及已关联收录来源不受影响。
- 管理后台「来源发现引擎 - 来源候选池」新增「清理无效候选」操作按钮与确认交互，清理完成后自动刷新并提示清理数量。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.51`。

## 验证

- `apps/api/tests/test_source_discovery.py` 新增 `test_admin_cleanup_source_candidates` 测试用例，验证权限拦截、状态过滤、安全保护及默认清理逻辑。
- `apps/web` Next.js 生产环境构建编译成功。
