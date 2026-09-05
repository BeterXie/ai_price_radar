# Release Notes v3.7.46

## 变更摘要

- **安全与可靠性**：移除管理密钥可用默认值，所有管理/Worker 密钥使用常量时间比较；收紧邮件地址、SMTP TLS、通知 Outbox 重试和收录状态并发处理。
- **公开数据边界**：公开目录、历史、店铺、Meta 和描述接口统一限制当前已发布快照、可见商品、有效报价与非隐藏来源；修复跨商品价格中位数和非有限金额处理。`dujiao_next` 继续按既有策略禁用前台与发布器。
- **来源发现与收录**：发现运行结束更新改为原子操作，修复候选去重、租约和失败统计；限制发现预算、GitHub 分页、输入长度与产品键，保留 Schema.org 人工审核边界。
- **解析与 Pipeline**：采用 `defusedxml`，限制 XML/JSON-LD 深度、节点、脚本和金额范围；统一分类器的库存否定词、期限边界、Pro 倍率与非目标品牌排除。
- **Web 体验**：区分 404 与 API 5xx，修复指南原型键访问、关注清单上限/阈值、公开 URL 私网地址校验、移动端菜单关闭和焦点轮廓。
- **运维**：Detector/Pipeline 依赖和 CI 安装路径同步，PostgreSQL 还原脚本拒绝超过 PostgreSQL 63 字节的数据库标识符。

## 验证

- API：327 passed，3 skipped
- Pipeline：317 passed
- Detector：76 passed，1 skipped
- Crawler：78 passed
- Web：60 passed，typecheck 与 production build 通过
