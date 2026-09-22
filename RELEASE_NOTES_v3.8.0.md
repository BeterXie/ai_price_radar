# Release Notes - v3.8.0

**发布日期**: 2026-09-22  
**发布版本**: 3.8.0

## 变更概述

v3.8.0 包含密码登录认证体系、全项目安全与依赖审计修复、通知 Worker 健壮性增强及多项关键修复：

1. **密码登录与安全认证体系**：
   - 采用 PBKDF2-HMAC-SHA256（600k 次迭代，遵循 OWASP 最佳实践），密码规则 8-64 位且须同时包含字母与数字。
   - 提供 `POST /api/v1/auth/password/login` 与 `POST /api/v1/user/password` 接口。
   - 验证码登录成功后引导首次设置密码（可跳过）；个人中心支持修改密码并吊销其他设备会话。
   - 针对暴力破解提供 IP 级数据库限流与邮箱级内存失败节流保护，统一防枚举错误响应。
2. **全项目安全、配置与依赖审计修复**：
   - 解决限流记录持久化、生产 CSP 策略对齐与各服务依赖配置一致性。
   - 修复 `sqlite_path_from_url` 对相对路径的处理异常。
3. **通知 Worker 韧性与站内公告清理**：
   - `notification_worker` 增加主循环异常捕获与指数退避重试，避免数据库抖动导致守护进程退出。
   - 自动清理站内公告历史版本遗留的 localStorage 孤儿键。
4. **数据库结构迁移 (v20)**：
   - 增加 `users.password_hash` 字段（`scripts/migrate_user_password_v20.py`，幂等安全）。

## 部署说明

- 生产数据库执行 `scripts/migrate_user_password_v20.py`。
- 按 `docs/QUICK_DEPLOY.md` 规范重新构建 `api`、`web`、`source-detector`、`importer`、`notification-worker` 与 `crawler`。
