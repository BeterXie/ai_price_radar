# Release Notes - v3.7.89

**发布日期**: 2026-09-18  
**发布版本**: `v3.7.89`

---

## 修复内容

v3.7.89 是 v3.7.88 的补丁版本，修复公开快照导出在生产环境失效的问题。

### 1. 快照导出写入失败（生产实测确认）

v3.7.88 部署时的发布门禁暴露出该问题：

```
Failed to export public snapshot 4718: [Errno 30] Read-only file system:
'/workspace/apps/web/public/data/v1'
```

发布流程 `scripts/refresh_remote.sh` 以只读方式挂载仓库（`-v "$ROOT:/workspace:ro"`），
而 `pipeline/publish_catalog.py` 在发布成功后调用 `export_public_snapshot()` 把快照
JSON 写入 `apps/web/public/data`，因此导出始终失败。发布本身（快照落库、报价入库）不受影响，
但 `/data/*` 公开数据文件无法更新。

修复方式：

- `scripts/refresh_remote.sh` 将 `apps/web/public/data` 以可写方式单独挂载
  （更具体的挂载覆盖只读父目录），并通过 `-e PUBLIC_DATA_DIR=...` 显式指定导出目录；
- `docker-compose.pricememo.yml` 的 `web` 服务挂载该目录，使其提供实时快照，
  而不是构建时烘焙进镜像的旧副本。

### 2. 影响范围与验证

- `/data/latest.json` 与 `/data/v1/snapshots/<id>.json` 会跟随每次发布刷新；
- API 侧 `/data/*` 端点读取同一共享目录（v3.7.88 已加入只读挂载）。

---

## 升级与迁移说明

- 本次发布无数据库结构变更。
- 无需执行任何迁移脚本。
- 部署后建议确认：一次完整刷新结束后 `apps/web/public/data/v1/snapshots/` 出现新的快照文件，
  且 `https://ai.pricememo.cn/data/latest.json` 的 `snapshot_id` 与最新发布一致。
