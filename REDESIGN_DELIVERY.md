# AI Price Radar 全站 UI 重构交付说明

## 设计方向

本次重构采用“数据工具 + 轻 SaaS”的统一视觉系统：雾白背景、深靛文字、紫蓝主色与少量青色信号色。目标不是把站点做成营销模板，而是在保持报价证据密度的前提下，让搜索、筛选、比较、阅读和管理场景拥有一致的产品体验。

## 页面覆盖

已通过共享布局、设计 token 和路由级组件覆盖以下页面族：

- 首页 `/`
- 报价目录 `/products`
- 商品详情 `/products/[slug]`
- 关注清单 `/watchlist`
- 教程中心 `/guides`
- 通用教程 `/guides/[guideSlug]`
- 品牌教程 `/guides/brands/[brand]`
- 商品教程 `/guides/products/[productSlug]`
- 交付教程 `/guides/delivery/[deliveryType]`
- 工作流教程 `/guides/workflows/[workflowSlug]`
- 商家提交 `/shops/submit`
- 商家详情 `/shops/[token]`
- 数据方法 `/methodology`
- 开发者 `/developers`
- 纠错 `/corrections`
- 关于 `/about`
- 隐私 `/privacy`
- 条款 `/terms`
- 安全 `/security`
- 管理后台 `/admin`
- JSON 转 Cockpit `/tools/json-to-cockpit`
- 全局 404、Header、Footer、社区提示、OpenGraph 分享图

## 主要变化

- 重做全局色彩、间距、圆角、阴影、焦点态与语义状态 token。
- 重做 Header、移动导航、Footer、Logo 图标和分享图。
- 首页升级为更清晰的搜索 + 实时报价 + 关键指标 + 证据说明结构。
- 产品列表、目录筛选、商品详情和报价表统一为更适合高密度数据的卡片/表格语言。
- 教程、政策、方法论等长文页面使用更舒适的阅读层级和内容容器。
- 管理后台、JSON 工具、表单和弹窗继续复用同一视觉系统。
- 保留原有业务逻辑、API 调用、路由结构、SEO metadata 与核心交互。
- 保留键盘焦点、跳转主内容、最小触控尺寸与 reduced-motion 支持。

## 校验结果

- 使用 TypeScript 5.8.3 parser 对 `apps/web/app` 与 `apps/web/components` 下 64 个 TS/TSX 文件进行语法解析：**0 个语法错误文件**。
- `globals.css` 花括号结构检查：**171 / 171，平衡**。
- 当前执行环境无法完成 `npm ci`：内部 npm 镜像对 `undici-types@6.21.0` 返回 404，因此未能在沙箱内继续执行完整 Next.js build。该错误发生在依赖下载阶段，与本次源代码语法检查无关。

## 本地运行

```bash
cd apps/web
npm ci
npm run typecheck
npm test
npm run build
npm run dev
```

若你的 npm registry 正常，上述命令会使用仓库原有 lockfile 安装依赖。
