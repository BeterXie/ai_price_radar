# SEO 收录与 AI 引荐监测

本项目的页面、站点地图和结构化数据由 Web 应用生成；Bing Webmaster Tools、IndexNow、百度搜索资源平台和 GA4 需要站点所有者在部署环境中提供验证 token、提交 token 或测量 ID。它们只能发送通知或记录来源，不能保证抓取、收录或 AI 摘要出现的时间。

## 站点验证 token

Web 应用支持通过运行时环境变量输出搜索引擎验证 meta 标签：

- `BING_SITE_VERIFICATION`：Bing Webmaster 的 `msvalidate.01` token；
- `BAIDU_SITE_VERIFICATION`：百度搜索资源平台的 `baidu-site-verification` token。

把 token 写入生产 Web 容器的 `.env` 后重新启动 Web 服务，再打开首页源代码确认对应的 `<meta>` 标签存在。token 不要提交到 Git，也不要写入客户端构建参数。

## IndexNow

1. 生成一个 IndexNow key，并把同一个值配置为 Web 运行时的 `INDEXNOW_KEY`。应用会在 `/indexnow-key.txt` 以纯文本提供它。
2. 部署后先确认 `https://ai.pricememo.cn/indexnow-key.txt` 返回的内容与 key 完全一致。
3. 在 PowerShell 7 中提交本次实际变更的规范 URL：

```powershell
$changed = @(
  "https://ai.pricememo.cn/",
  "https://ai.pricememo.cn/products/claude-pro",
  "https://ai.pricememo.cn/sources/16688",
  "https://ai.pricememo.cn/sitemap.xml"
)
pwsh -File .\scripts\submit-indexnow.ps1 -Url $changed
```

只提交已部署且可返回 200 的 URL；通知被接受不等于 URL 已被抓取或收录。

## Bing Webmaster Tools

在已验证的 Bing Webmaster 属性中提交 `https://ai.pricememo.cn/sitemap.xml`。若使用 API，将 `BING_WEBMASTER_API_KEY` 配置在本机环境中，然后运行：

```powershell
pwsh -File .\scripts\submit-bing-sitemap.ps1
```

脚本只提交站点地图，不会登录、修改站点设置或替代属性验证。

建议顺序：先在 Bing Webmaster Tools 验证 `https://ai.pricememo.cn`，再提交 `https://ai.pricememo.cn/sitemap.xml`；站点验证 token 可以通过 `BING_SITE_VERIFICATION` 自动放入页面。

## 百度搜索资源平台

在百度搜索资源平台添加并验证 `https://ai.pricememo.cn`。验证 token 可以通过 `BAIDU_SITE_VERIFICATION` 自动放入页面；百度的主动推送 token 只保存在本机或 CI 环境，不进入 Web 容器：

如果百度后台要求文件验证，当前文件材料保存在本机 `seo/baidu_verify_codeva-27l7NEdkV0.html`，并已在 `docs/QUICK_DEPLOY.md` 固定为每次发布时单独上传到 Web 镜像的 `public` 根目录。它被 `.gitignore` 排除，不应提交到 GitHub。

```powershell
$changed = @(
  "https://ai.pricememo.cn/",
  "https://ai.pricememo.cn/products/chatgpt-plus",
  "https://ai.pricememo.cn/sources/16688",
  "https://ai.pricememo.cn/sitemap.xml"
)
pwsh -File .\scripts\submit-baidu-urls.ps1 -Url $changed
```

脚本只接受本站 HTTPS URL，并把 URL 作为纯文本提交到百度主动推送接口。接口返回“成功”只代表百度接受了推送请求，不代表 URL 已经抓取或收录。

## GA4 AI 引荐

配置 `NEXT_PUBLIC_GA_MEASUREMENT_ID` 后，应用会记录不含查询参数的页面路径，并在首次进入页面的外部 referrer 命中 `ai`、`chatgpt`、`claude`、`bard`、`gemini`、`perplexity`、`copilot` 或 `poe` 时发送 `ai_referral` 事件。事件参数为：

- `ai_referral_source`：外部 referrer 主机名；
- `ai_referral_term`：命中的分类词；
- `ai_referral_path`：外部 referrer 路径，不含查询参数；
- `referral_medium`：固定为 `referral`。

在 GA4 管理后台为 `ai_referral_source` 和 `ai_referral_term` 建立事件级自定义维度，然后在探索中筛选事件名 `ai_referral`，按日期、来源主机名和落地页路径观察趋势。GA4 的默认流量归因仍以实际 referrer、UTM 和平台规则为准；如果 AI 平台隐藏或改写 referrer，需要在链接侧补充 UTM 才能完整识别。
