# 店铺收录与邮件通知开发任务

> 本文记录最初只覆盖 LDXP 的第一阶段设计。当前多来源流程以 [Architecture](ARCHITECTURE.md)、[Source connectors](CONNECTORS.md) 和 `CONTEXT.md` 为准：公开提交从 `submitted` 异步检测，Dujiao-Next/Merchant JSON 经批准后进入 `approved`，成功参与原子快照后才成为 `published`；下文的统一 `pending_review -> queued` 不适用于这些来源。

## 目标

把当前“关闭一条 `shop_request` Report”的假收录流程，改造成可追踪、可重试、可通知的真实收录流程。第一阶段必须完整覆盖 LDXP 人工申请；Merchant JSON Feed 复用同一状态机，连接器消费可作为独立后续任务，不得在未发布商品时标记为已收录。

## 领域边界

- 店铺收录申请：申请人提交、等待管理员初审的记录。
- 候选来源：初审通过、等待系统验证的来源。
- 已收录店铺：验证成功、发现目录范围内商品且已经发布的店铺。
- 初审通过不等于正式收录。
- `Report` 继续承载纠错和风险反馈；新店铺申请使用独立收录模型。历史 `shop_request` Report 通过迁移转成收录申请。

## 状态机

```text
pending_review
  -> queued
  -> validating
  -> validated
  -> onboarded

pending_review -> rejected
validating -> no_products
validating -> validation_failed
no_products | validation_failed -> queued
```

- `validated` 表示抓取成功且发现目标商品，但还未确认发布。
- `onboarded` 只能在商品成功同步进已发布目录后设置。
- Worker 领取任务必须有租约；租约过期后允许安全重领。

## TASK-01：数据模型与迁移

新增 `source_intakes`：

- `id`
- `report_id`，仅用于关联历史申请，可空、唯一
- `source_type`：`ldxp` / `merchant_feed`
- `source_key`：规范化后的唯一键；LDXP 使用小写 token，Feed 使用规范化 URL
- `source_url`
- `shop_name`
- `contact_email`
- `note`
- `origin`：`manual` / `auto_discovery`
- `status`
- `decision_note`
- `failure_reason`
- `attempt_count`
- `product_count`
- `lease_expires_at`
- `approved_at`、`started_at`、`finished_at`
- `created_at`、`updated_at`

唯一约束：`source_type + source_key`。所有状态转换必须幂等。

新增 `notification_outbox`：

- `id`
- `event_type`
- `recipient`
- `subject`
- `text_body`
- `status`：`pending` / `sending` / `sent` / `failed`
- `attempt_count`
- `next_attempt_at`
- `last_error`
- `dedupe_key`，唯一
- `created_at`、`sent_at`

新增幂等 PostgreSQL 迁移脚本。历史 `shop_request` Report 的迁移规则：

- 已存在对应正式 Shop：`onboarded`。
- 原状态为 `rejected`：`rejected`。
- 其余状态：`pending_review`。这会让旧版“已处理但未实际收录”的申请重新出现在收录审核列表。

## TASK-02：公开申请

- 保留 `POST /api/v1/shop-requests` 路径。
- 联系邮箱改为必填、使用邮箱格式校验；不再接受微信等任意联系方式作为结果通知地址。
- 新申请直接创建 `SourceIntake`，不再创建通用 Report。
- 已知店铺返回 `already_known`；存在未终结申请返回 `already_pending`。
- 创建成功后，在同一数据库事务写入两封 Outbox 邮件：管理员新申请通知、申请人提交回执。
- 页面把“联系方式”改为“联系邮箱”，使用 `type=email`、必填，并说明仅用于申请通知。

## TASK-03：管理员审核

新增独立接口，不再通过通用 Report PATCH 审批店铺：

- `GET /api/v1/admin/source-intakes`
- `POST /api/v1/admin/source-intakes/{id}/approve`
- `POST /api/v1/admin/source-intakes/{id}/reject`
- `POST /api/v1/admin/source-intakes/{id}/retry`

规则：

- 批准：`pending_review -> queued`，写入“已通过初审，等待验证”邮件。
- 驳回：仅允许 `pending_review -> rejected`，原因必填，写入申请人邮件。
- 重试：仅允许 `no_products` 或 `validation_failed -> queued`。
- 重复操作返回当前结果，不重复发邮件。
- 后台将收录申请与纠错 Report 分区展示。
- 店铺申请按钮使用“批准并验证”“驳回”“重新验证”，禁止“已处理”。
- 展示状态、商品数、重试次数、失败原因和邮件状态。

## TASK-04：邮件 Outbox Worker

- 生产优先使用 Resend API；保留 Python 标准库 SMTP 作为本地和回退发送通道。
- 增加独立长运行 Worker 服务轮询 Outbox；API 请求中不得直接调用 Resend 或连接 SMTP。
- 单封发送失败不能回滚业务事务。
- 失败按 1、5、30 分钟退避，达到上限后保留 `failed`，后台允许重发。
- Resend API Key 和 SMTP 密码不得进入日志、API 响应或仓库。
- Resend/SMTP 均未配置时 API 可启动，邮件保持待发送并输出不含隐私数据的明确诊断。

邮件事件：

- `shop_request.submitted.admin`
- `shop_request.submitted.applicant`
- `shop_request.approved`
- `shop_request.rejected`
- `shop_intake.onboarded`
- `shop_intake.no_products`
- `shop_intake.validation_failed`

## TASK-05：LDXP 验证桥接

API 增加使用独立 Worker Key 的内部接口：

- 原子领取排队中的 LDXP 申请并设置租约。
- 回报验证结果，校验合法状态转换。

爬虫在每次 `scan` 开始前：

- 从 API 领取人工申请。
- 写入现有 crawler SQLite `candidates`，保留 `intake_id`，人工申请优先扫描。
- 扫描成功且命中商品：回报 `validated`。
- 扫描成功但无命中：回报 `no_products`。
- 阻断或失败：回报 `validation_failed` 和可公开的简短原因。

`sync_ldxp.py` 必须把成功导入且发布的 `intake_id` 从 `validated` 更新成 `onboarded`，并写入最终结果邮件。抓取完成但同步失败时不得发送“已收录”。

API 不得直接写 crawler SQLite。内部接口使用与管理员 Key 不同的 Secret。

## TASK-06：配置和文档

更新 `.env.example`、Compose 和部署文档，至少包括：

- `SHOP_INTAKE_ADMIN_EMAILS`
- `INTAKE_WORKER_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_STARTTLS`

不得写入真实邮箱密码。数据库迁移必须进入发布和生产部署门禁。

## TASK-07：测试与验收

API 测试至少覆盖：

- 邮箱必填和格式校验。
- URL 规范化、已知店铺、重复申请。
- 新申请与两封 Outbox 邮件同事务提交。
- 批准、驳回、重试的合法与非法状态转换。
- 重复审批不会重复发送邮件。
- Worker 成功、失败、退避、重发和敏感错误清洗。
- 内部 Worker Key 鉴权、任务领取租约和过期重领。
- 历史 Report 迁移，包括旧“resolved”申请重新进入待审核。

爬虫和 Pipeline 测试至少覆盖：

- 人工申请写入候选库且优先扫描。
- 命中、无商品、失败三类回报。
- 只有同步发布成功才转成 `onboarded`。

Web 验收：

- 类型检查和生产构建通过。
- 联系邮箱为必填。
- 收录申请有独立列表和准确按钮。
- 管理员可以看到处理结果、失败原因和邮件状态。

全局验收：

- 原有 API、Pipeline、爬虫测试不回归。
- Python 编译检查通过。
- 迁移脚本可重复执行。
- 不修改无关页面和报价计算逻辑。
