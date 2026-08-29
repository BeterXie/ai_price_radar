# SEO 收录与 AI 引荐监测

本项目的页面、站点地图和结构化数据由 Web 应用生成；IndexNow、Bing Webmaster Tools 和 GA4 需要站点所有者在部署环境中提供凭据或测量 ID。它们只能发送通知或记录来源，不能保证抓取、收录或 AI 摘要出现的时间。

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

## GA4 AI 引荐

配置 `NEXT_PUBLIC_GA_MEASUREMENT_ID` 后，应用会记录不含查询参数的页面路径，并在首次进入页面的外部 referrer 命中 `ai`、`chatgpt`、`claude`、`bard`、`gemini`、`perplexity`、`copilot` 或 `poe` 时发送 `ai_referral` 事件。事件参数为：

- `ai_referral_source`：外部 referrer 主机名；
- `ai_referral_term`：命中的分类词；
- `ai_referral_path`：外部 referrer 路径，不含查询参数；
- `referral_medium`：固定为 `referral`。

在 GA4 管理后台为 `ai_referral_source` 和 `ai_referral_term` 建立事件级自定义维度，然后在探索中筛选事件名 `ai_referral`，按日期、来源主机名和落地页路径观察趋势。GA4 的默认流量归因仍以实际 referrer、UTM 和平台规则为准；如果 AI 平台隐藏或改写 referrer，需要在链接侧补充 UTM 才能完整识别。
