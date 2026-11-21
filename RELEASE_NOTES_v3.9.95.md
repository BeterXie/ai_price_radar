# v3.9.95

将采集私有网关从 Docker 的 internal 网络移到专用 `ai-price-radar_collector_gateway` 桥网络。该网络只连接 API 和路由网关，保留宿主机 loopback 18083 的转发；避免 internal 网络不创建端口监听，同时不把网关加入包含数据库的默认网络。

本版本包含 v3.9.94 的网关能力修复和 v3.9.93 的 Oracle 采集迁移。按 `docs/QUICK_DEPLOY.md`、`docs/COLLECTOR_DEPLOY.md` 完成构建、迁移和实际采集发布验收。
