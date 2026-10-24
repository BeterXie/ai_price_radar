# Release Notes - v3.9.16

发布日期：2026-10-25

本版本包含 v3.9.15 的套餐分类、搜索筛选、前台中转站申请与后台审核、加密凭据、三协议探活及近 24 小时稳定性统计，以及 OpenCodeReview 评审修复和 Next.js 16.4.3 安全升级。功能说明与评审记录见 `RELEASE_NOTES_v3.9.15.md`、`docs/REVIEW_v3.9.15.md`。

v3.9.15 生产尝试在切换容器前停止：迁移导入应用模型时读取挂载的 root-only `.env`，非特权 API 镜像无权读取。旧容器继续提供 v3.9.14，源码、镜像标签和调度均已恢复，数据库没有执行该迁移的结构变更。

v3.9.16 将中转站迁移与应用初始化解耦，通过独立 SQLAlchemy 表定义创建检测样本表；只使用显式数据库连接，不读取应用 `.env`。不更改现有环境文件权限，不提高 API 镜像权限。增加独立 CLI 子进程回归，验证工作目录存在不可解析 `.env` 时仍可迁移。

部署仍严格执行 `docs/QUICK_DEPLOY.md`：临时 PostgreSQL 16 连续演练 v22 两次；新 API 切换前使用新镜像运行 `python scripts/migrate_relay_monitoring_v22.py`。从 v3.9.14 升级时需要此迁移。重建 API、Web、来源检测、Importer、Crawler，使用当前版本执行完整多来源发布并验收。保留已有凭据加密密钥，不重建 PostgreSQL。
