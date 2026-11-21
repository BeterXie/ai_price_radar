# v3.9.96

支持分阶段迁移：`COLLECTOR_LDXP_ENABLED=false` 时，Oracle Worker 只领取已批准的非 LDXP 来源；主站继续通过 `refresh_remote.sh ldxp-only` 扫描和发布 LDXP，并保留旧浏览器会话与回滚路径。非 LDXP 批次不会启动浏览器扫描。

新增非 LDXP 入队 timer，主站 API 和发布器仍是统一快照与通知权威。待 LDXP 站点验证完成后，再打开开关并迁移浏览器扫描。
