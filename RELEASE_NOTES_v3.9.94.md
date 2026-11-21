# v3.9.94

修复独立采集私有网关在非 root、cap_drop ALL 与 no-new-privileges 下无法启动的问题。网关使用仅移除 Caddy 二进制文件能力标记的专用镜像，继续监听容器 8080 与主站 loopback 18083。CI 使用相同的权限限制实际运行网关程序并验证配置。

本版本包含 v3.9.93 的全部独立采集功能及 v28 迁移要求。主站在构建阶段额外运行带 docker-compose.collector-control.yml 的 `build collector-gateway`；继续按 QUICK_DEPLOY.md 和 COLLECTOR_DEPLOY.md 完成甲骨文切换验收。
