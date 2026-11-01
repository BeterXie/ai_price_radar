# 百度统计

`apps/web/app/layout.tsx` 全站挂载 `SiteAnalytics`。组件使用百度后台为 `ai.pricememo.cn` 提供的公开统计标识 `0abf0f3c54963dc5874f6a4ebcbfaf37`，不需要 API 密钥或额外构建变量。

## 运行方式

- 仅在 `ai.pricememo.cn` 的公开页面自动异步加载 `https://hm.baidu.com/hm.js?0abf0f3c54963dc5874f6a4ebcbfaf37`，无需访客操作或确认弹窗。
- 隐私页提供当前浏览器的开启 / 停用开关。继续尊重旧版百度或百度与 Google 联合提示的明确拒绝记录；无法读取浏览器存储时不加载。仅有 Google 的选择不影响百度开关，Google 仍要求单独明确允许。
- Next.js 首屏和客户端路由切换统一通过 `_trackPageview` 记录；脚本加载前设置 `_setAutoPageview=false`，避免自动 PV 与手动 PV 重复。
- 账号、管理、认证和凭据转换工具页面不主动上报 PV；查询参数沿用白名单，搜索词只保留 `q=present`。
- 本地和预览域名不加载百度统计，避免测试访问混入正式报表。
- 仓库中的 Caddy CSP 模板允许百度脚本域名 hm.baidu.com、hmcdn.baidu.com 与采集域名 hm.baidu.com。部署到启用该 CSP 的代理时，应同步使用新版模板；正式站以实际浏览器请求验收。

## 发布后验证

按 `docs/QUICK_DEPLOY.md` 完成正常发布后，在无历史选择的浏览器打开正式站，不点击任何确认按钮，核对脚本请求和百度采集请求是否成功；再通过站内链接切换页面，检查是否各产生一次 PV。另检查历史拒绝及隐私页停用后的页面不加载百度脚本。

在[代码安装检查](https://tongji.baidu.com/main/setting/10000742431/home/js/check?siteId=23652215)和“最新访客 / 受访页面”报告核对。百度安装页说明一般约 20 分钟后可查看数据；实际浏览器请求和后台报告作为采集验收依据。

这是客户端统计。停用分析、浏览器拦截、网络失败或禁用 JavaScript 都可能造成漏记，不能等同于服务器全部访问量。本次接入不配置自定义业务事件或转化漏斗。

官方参考：[PV 跟踪部署说明](https://tongji.baidu.com/holmes/Analytics/技术接入指南/JS%20API/JS%20API部署说明/PV跟踪)。
