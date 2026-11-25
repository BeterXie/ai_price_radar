# Microsoft Clarity

`https://ai.pricememo.cn` 使用项目「pricememo主页」，公开项目 ID 为 `zj9ygr64oc`，无需 API 密钥、NPM 依赖或额外构建变量。

## 运行方式

- 默认在 `ai.pricememo.cn` 异步加载 `https://www.clarity.ms/tag/zj9ygr64oc`，不显示 Clarity 许可弹窗。Clarity 自行跟踪公开页面导航，同一文档不重复插入脚本或手动发送 PV。
- 百度现有独立偏好和渠道归因保持不变；如果另行配置 Google Analytics，只对 Google 保留原有许可选择。
- 脚本前排队发送 Consent V2：`analytics_Storage: granted`、`ad_Storage: denied`。本地、预览、主站根域名别名及四个品牌站不加载此项目。
- 账号、管理、认证、关注清单、来源收录申请、凭据转换工具页面不加载录制脚本。`AnalyticsPageBoundary` 阻止私密 UI 在已加载或正在下载 SDK 的文档内渲染，再重载为没有 Clarity 的文档。单独卸载 script 或调用 `stop` 不足以隔离，SDK 会在 SPA 导航后自行重启。
- 登录弹窗和账户昵称用 `data-clarity-mask` 遮罩；不调用 Identify API，也不主动传递账号标识。
- Clarity 自动采集 URL（含查询参数）和交互，不经过百度/GA 的 `buildAnalyticsPath` 手动过滤。公开 URL 不应包含凭据；项目级 URL 参数遮罩按官方 FAQ 联系 Clarity 支持。

## 发布与验收

遵循 [生产发布流程](QUICK_DEPLOY.md) 和 [多品牌发布](MULTI_BRAND_DEPLOY.md)。若实际代理有 CSP，应允许 `https://*.clarity.ms` 的脚本及连接、`https://c.bing.com` 的连接；仓库模板已更新，原有图片 `https:` 允许像素请求。

1. 打开公开页面时跟踪脚本、SDK 和 `*.clarity.ms/collect` 请求成功；本地、预览和品牌域名不发送到这个项目。
2. 站内切换公开页面时脚本只加载一次；进入私密页面后文档重载，页面正常呈现且没有 Clarity 脚本。
3. 在 [Clarity 项目](https://clarity.microsoft.com/projects/view/zj9ygr64oc/gettingstarted) 确认收到数据，再查看仪表板、录制和热度地图。安装页提示首批数据可能最多需要 2 小时；脚本 HTTP 200 不等同于报表已收到数据。

统计只覆盖公开页面且成功加载脚本的访问，不等于服务器全部访问量。

官方参考：[客户端 API 与遮罩](https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-api)、[Consent V2](https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-consent-api-v2)、[CSP](https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-csp)、[SPA 重启实现](https://github.com/microsoft/clarity/blob/master/packages/clarity-js/src/core/history.ts)。
