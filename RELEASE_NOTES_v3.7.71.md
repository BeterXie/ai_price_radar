# AI Price Radar v3.7.71 — Report Status Filtering & Correction UX Enhancement

## 概述
本版本优化了后台“纠错与风险反馈”模块的交互与接口，全面支持多状态筛选与历史归档回溯，并在前台公开纠错记录页面提供了直接提交入口。

## 核心改进

1. **后台纠错与风险反馈多状态二级筛选（`apps/web/components/admin-panel.tsx`）**：
   - 增加【待处理】（带未处理红标计数）、【已处理】、【已驳回】、【全部记录】二级切换按钮与即时刷新功能。
   - 解决以往一旦将反馈标记为处理/驳回后在后台无法查阅历史的问题。
   - 已处理卡片展示当时的公开事实摘要、商家公开回复和处理时间戳；已驳回卡片展示驳回记录与时间戳。

2. **管理端 API 全量状态查询支持（`apps/api/app/routers/admin.py`）**：
   - `GET /api/v1/admin/reports` 增加对 `status=all` 的支持，同时兼容 `open`、`resolved`、`rejected` 状态过滤。
   - 补充 `apps/api/tests/test_reports.py` 自动化测试套件（`test_admin_reports_status_filtering`）。

3. **公开纠错记录页提交表单增强（`apps/web/app/corrections/page.tsx`）**：
   - 在 `/corrections` 页面底部挂载 `ReportForm`，方便专门查看纠错记录的用户直接提交新的反馈。
