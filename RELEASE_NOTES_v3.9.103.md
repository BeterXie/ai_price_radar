# v3.9.103

修复 16688 商品采集已迁到 Oracle、收录安全检测却仍从主站访问的问题。申请和发现候选按官方 URL 分流：Oracle 只领取 16688，主站检测其余来源，LDXP 浏览器扫描仍在主站。

部署配置 `DETECTOR_16688_ON_ORACLE=true`、主站 `DETECTOR_SCOPE=other`，Oracle 同时运行 collector 与 scope=16688 的 detector。旧 Worker 的默认领取也无法抢走 Oracle 任务。16688 验证获得适合跨区访问的超时预算；限速等待仍延期，不标记店铺无效；单条回报被拒绝不再中断整批。

无数据库结构变更。按 QUICK_DEPLOY.md 和 COLLECTOR_DEPLOY.md 部署并用真实申请完成验证、收录与公开报价检查。
