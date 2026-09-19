# Release Notes - v3.7.92

**发布日期**: 2026-09-19  
**发布版本**: `v3.7.92`

---

## 变更概述

v3.7.92 集中完成了系统安全加固，包括会话凭据机制升级、QQ 机器人凭据 AES-GCM 静态加密存储、原子绑定修复与防并发重放、超期日志隐私合规自动清理，以及关键依赖漏洞修复。

---

## 核心变更

### 1. 凭据加固与静态加密
- 引入 `SESSION_SECRET_KEY`，启动时平滑迁移旧版会话令牌哈希；
- 新增 `credential_crypto.py`，支持 `BOT_SECRET_ENCRYPTION_KEY` 通过 AES-256-GCM（AEAD 认证加密）对第三方机器人凭据进行静态加密存储，解密失败自动降级安全保护；
- 生产预检脚本 `production_preflight.py` 强化对会话密钥长度（至少 32 字节）、文档接口（`API_DOCS_ENABLED=false`）及敏感开关的合规校验。

### 2. QQ 机器人绑定原子性与防重放
- 修复跨数据库引擎（SQLite / PostgreSQL）下的绑定认领竞争条件，统一采用原子事务校验与防误报机制；
- 移除多余的过期索引定义，规避表结构冗余。

### 3. 隐私保护与依赖漏洞修复
- 新增 `privacy.py` 服务，在应用启动生命周期内自动清理超期（默认 90 天）的操作日志与会话数据；
- 修复 pytest PYSEC-2026-1845 依赖漏洞，同步锁定升级周边生态依赖包。

---

## 升级与迁移说明

- 本次发布无手工数据库迁移脚本，应用在启动时通过内部服务（`migrate_legacy_session_tokens`、`migrate_bot_credentials`）自动执行平滑数据幂等迁移；
- 生产服务器 `.env` 已预先注入 `SESSION_SECRET_KEY`、`BOT_SECRET_ENCRYPTION_KEY` 与 `API_DOCS_ENABLED=false`；
- 遵循 `docs/QUICK_DEPLOY.md` 生产标准部署：
  - 生产重建 `api`、`web` 容器。
