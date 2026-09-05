# Release Notes v3.7.48

## 变更摘要

- 为生产 Importer 镜像补充显式 Python 包镜像参数，避免默认 Docker 构建网络无法解析 SQLAlchemy 依赖。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.48`。

## 验证

- 生产 Compose 配置包含 Importer 的 `PIP_INDEX_URL`。
