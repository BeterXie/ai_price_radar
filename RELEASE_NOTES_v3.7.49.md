# Release Notes v3.7.49

## 变更摘要

- 修复完整远程刷新路径无条件运行 Dujiao-Next 发现的问题；默认继续保持 Dujiao 禁用，只有显式设置 `ENABLE_DUJIAO_DISCOVERY=true` 才运行。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.49`。

## 验证

- `scripts/tests/test_multi_source_entrypoints.py` 覆盖完整刷新禁用分支。
