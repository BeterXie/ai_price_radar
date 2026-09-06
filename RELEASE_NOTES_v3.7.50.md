# Release Notes v3.7.50

## 变更摘要

- 新增「商务合作 / 广告投放」落地页（`/advertise`）与官方联系邮箱 `info@ai.pricememo.cn`。
- 后端新增 `SystemSetting` 键值系统设置表，及管理端配置接口（`GET /api/v1/admin/settings`、`PATCH /api/v1/admin/settings`）。
- 公共元数据接口（`/api/v1/meta`）集成 `advertise_enabled` 状态。
- 管理后台（`/admin`）新增「功能与运营配置」专区与商务合作独立开关，默认关闭（部署后不显示），支持后台随时一键开启或关闭。
- 前台页脚、移动端菜单、店铺申请页及关于页均根据开关动态渲染商务合作入口；关闭状态下直接访问 `/advertise` 触发 404。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.50`。

## 验证

- `apps/api/tests/test_admin_settings.py` 覆盖设置默认状态、修改与元数据同步逻辑。
- `apps/api` 328 项 pytest 测试全部通过。
- `apps/web` TypeScript 类型检查通过，60 项测试全部通过，Next.js 生产打包成功。
