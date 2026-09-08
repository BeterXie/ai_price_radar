# Release Notes v3.7.56

## 变更摘要

- **16688 及非 LDXP 目录发布店铺正式收录通知补齐**：
  - 在 `pipeline/publish_catalog.py` 快照发布逻辑中新增 `enqueue_published_intake_notifications`，当 16688、WooCommerce 等平台申请入库并发布到快照时，自动为留有联系邮箱的商户入队《店铺已正式收录》（`shop_intake.onboarded`）通知邮件，附带专属收录页面链接与已上架商品数。
  - 支持 `shop_intake.no_products` 通知，当未拉取到目标商品时提醒申请人。
  - 新增 `pipeline/backfill_published_intake_emails.py` 一键补发脚本，自动扫描存量已发布店铺并补发正式收录喜报。
- **管理后台邮箱状态透明度提升**：
  - 在 `apps/web/components/admin-panel.tsx` 中明确区分留有邮箱的商户与网络爬虫自动发现的店铺，明确标注“无联系邮箱（系统爬虫自动发现，不发送邮件通知）”，彻底消除管理员误判。
- **搜索引擎验证与爬虫指令增强**：
  - 在 `apps/web/app/layout.tsx` 中补充 Bing 与 Baidu 站长验证标签支持。
  - 增强 `robots` 与 `googleBot` 指令，提升新页面收录效率。

## 验证

- Pipeline 319 项单元与集成测试全部通过。
- 后端 API 332 项测试全部通过。
- 前端 63 项单元测试通过，Next.js 65 个页面静态编译成功。
