# 账号套餐、搜索与中转站监测

套餐名称核对日期：2026-10-24。分类表示商家商品原文声明的套餐，不能代替对实际账号权益的核验。

## 套餐对应

| 品牌 | 分类规则 | 官方来源 |
| --- | --- | --- |
| OpenAI | Free、Go、Plus、Pro 5x、Pro 20x 分开；未注明倍率的 Pro 独立展示；Business / 原 Team、Edu、Enterprise 分开；K12 仅保留为商家标签 | [ChatGPT Pricing](https://learn.chatgpt.com/docs/pricing) |
| Claude | Pro、Max 5x、Max 20x、倍率未注明的 Max、Team、Enterprise 分开；5x 是 Max 相对 Pro 的用量档位 | [Claude Pricing](https://claude.com/pricing) |
| Gemini | Google AI Plus、Pro、Ultra 及明确标注的 Ultra 倍率分开；Advanced 保留为历史名称；Gemini 2.5 Pro 等模型名不能作为账号 Pro 套餐的证据 | [Google AI Plans](https://one.google.com/intl/en/about/google-ai-plans/) |
| Cursor | 当前 Plus、Premium、Super、Ultra、Teams 与仍在商品中出现的 Pro、Pro+ 分开；不推断不同版本权益相同 | [Pricing](https://cursor.com/pricing)、[Models and pricing](https://cursor.com/docs/models-and-pricing) |
| Grok | 当前 Plus、Premium、Super、Ultra 分开；商家仍标注 SuperGrok、SuperGrok Heavy 时保留独立分类；X Premium 是另一个产品系列 | [xAI Pricing](https://x.ai/pricing) |

明确标题优先于店铺分类；Free、底号、未订阅账号不会因店铺分类或营销描述变成高等级订阅。Claude、Gemini、Cursor、Grok 的订阅没有明确等级时单独列为“等级未注明”，不猜测为 Pro。套餐、交付方式、周期、质保继续分别记录和筛选。

`apps/api/app/services/account_plans.py` 集中定义套餐及对应关系，采集分类与后台重新分类共用 API 的身份判断。前端筛选和机器人查询同步更新。现有 `claude-pro-20x` URL 仍在使用，展示名称改为 Claude Max 20x；`grok-super` 对应 SuperGrok，新的 Grok Super 使用 `grok-plan-super`。

套餐核对与价格核对分开。未核实的新价格不填入官方价格参考；原有价格保留其核实日期。Google AI Pro 的价格参考只挂在 `gemini-pro`，不再套用到历史 Advanced 商品。

## 搜索与筛选

关键词按空格拆分，多个词取交集，每个词可跨商品标题、标准商品名称、品牌和店铺名称匹配。支持 OpenAI / ChatGPT、Gemini / Google AI、克劳德等别名；`%`、`_` 和反斜杠按普通字符搜索。

关键词和来源、交付方式、周期、库存、价格等筛选共同生效。品牌目录、具体套餐详情、分组展开与后续分页保留同一搜索范围。

## 中转站申请和审核

在 `/shops/submit?type=relay` 提交官网、名称、Base URL、检测密钥、接口协议、模型 ID、联系邮箱。邮箱必须与已验证的登录账号一致，并确认有权提交。使用现有中转站表和后台管理界面，申请初始为待审核、未上线；批准并上线后才可公开和监测。驳回会关闭监测。

后台“广告与中转站 → 中转站”可查看申请、编辑、批准、驳回、上下线及检测。编辑密钥留空保留原值；输入新密钥替换。相同官网重复申请不会覆盖已有配置或密钥。公开结果不会返回 Base URL、密钥、联系邮箱和申请说明。密钥也不会出现在校验错误中。

凭据复用现有 AES-GCM 加密服务。部署时需配置 `BOT_SECRET_ENCRYPTION_KEY`（至少 32 字节随机材料）；现有密钥轮换通过 `BOT_SECRET_ENCRYPTION_PREVIOUS_KEYS` 解密历史密文，更新站点密钥时使用当前主密钥。缺少有效的凭据加密配置时，录入密钥会失败。

## 探活和稳定性

支持三种协议：OpenAI 兼容 Chat Completions、Anthropic Messages、Gemini 原生 generateContent。Base URL 保留服务商要求的前缀，自动补齐协议路径；应填写根地址而非完整请求路径。仅连接公开 HTTPS 443，使用现有客户端校验并固定 DNS 解析后的公网 IP、验证 TLS、不跟随重定向，并限制时间与响应大小。

审核通过、上线且开启监测的站点，每小时最多发送一次简短文本生成请求；手动检测共用该限制。请求可能扣费，建议提供专用低额度密钥，选择支持简短文本输出的低成本非思考模型。仅返回模型列表或 HTTP 200 而没有有效文本，不算探活成功。只支持 Responses 的上游应先提供兼容 Chat Completions 的地址和模型；否则会显示配置异常。

展示最近检测状态与耗时、近 24 小时有效采样数、请求成功率，以及成功请求耗时的 P95。401 / 403 为密钥或权限诊断，400 / 404 / 405 / 422 为配置诊断，这些诊断不计入成功率分母；限流、超时、连接失败、服务错误和无效响应计入失败。成功率是对该密钥、协议和模型的采样结果，不代表全站 SLA、所有模型或模型能力。超过两小时未更新标记为过期；没有样本不展示成功率。

v3.9.17 的展示卡片进一步参考 PriceAI 的 [`StationCard`](https://github.com/dimthink/PriceAI/blob/main/src/components/TransitStationExplorer.tsx#L809) 与 [`TransitAvailabilityStrip`](https://github.com/dimthink/PriceAI/blob/main/src/components/TransitAvailabilityStrip.tsx)，将站方报价和真实稳定性采样并排展示，模型列表及站点介绍折叠展开。公开样本只包含当前配置近 24 小时最近 24 次检测的时间、状态和耗时，不含请求地址、凭据或响应正文。每格对应一次真实检测，按时间从旧到新；空格保持为空，不用汇总成功率生成虚构的历史记录。仍使用本项目的 24 小时单模型采样口径，没有引入 PriceAI 的多模型倍率、用户口碑或站方公开监控数据。

站点图标优先识别官网首页声明的 favicon（包括 apple-touch-icon），再尝试 `/favicon.ico`，加载失败显示站名首字。卡片始终保留站名和域名，通用程序图标不作为商家身份验证。图标由本站服务端获取，浏览器不直连商家；仅接受已审核且启用的站点，不使用检测 Base URL、邀请链接参数或密钥。

复用固定公网 IP 的安全 HTTPS 客户端，禁止重定向，单响应最多 256 KiB、外网获取整轮最多 8 秒、最多 3 个图片候选；只返回 PNG、ICO、GIF、WebP、JPEG，不托管远端 SVG/HTML。成功缓存 24 小时、失败缓存 15 分钟，最多 128 个官网及 4 个并发获取。同站点并发合并等待，容量等待最多 8 秒，暂时繁忙返回不可缓存的 503 和 Retry-After，前端最多补试两次并保留首字显示。

修改 Base URL、密钥、协议或模型后，统计从新配置重新开始。样本保留 30 天；不存储上游响应正文、异常文本或请求密钥。监测在 API lifespan 中运行，通过数据库条件更新领取到期任务，避免多个 API 进程重复领取同一轮检测。

## 数据生效与验证

生产切换 API 前按发布说明执行 `python scripts/migrate_relay_monitoring_v22.py`；该脚本复用启动升级逻辑，仅修改中转站表及检测样本表，并要求先在临时 PostgreSQL 16 重复演练。既有中转站保持已审核、监测默认关闭。

API 启动自动补齐 SQLite / PostgreSQL 字段和样本表、注册新套餐，并恢复以前被种子和导入程序强制隐藏的 `chatgpt-pro` 分类。已有报价的分类在下一次采集时更新，也可使用后台“重新分类”；批量重新分类继续保留 `manual_override`。单条重新分类是明确的人工重算操作。公开页面复用现有缓存，审核变化可能需约一分钟后刷新可见。

自动化回归覆盖套餐对应、搜索交集与分页、申请权限与重复录入、密钥加密和不回显、审核隔离、三协议请求格式、异常响应、统计窗口、任务领取、旧表升级，以及携带鉴权头的公网连接和重定向防护。

本地浏览器验证使用独立临时 SQLite 数据库、假密钥和模拟检测样本，关闭后台任务。真实商家 Base URL / 密钥未提供，因此未执行付费外网模型探活；上线后需用商家授权的检测凭据确认实际接口兼容性。

参考了 [PriceAI](https://github.com/dimthink/PriceAI) 的功能思路。其当前许可证为 PriceAI Source Available License 1.0，包含商业托管等限制，不能视为通用开源许可；本次独立实现，没有复制其代码。

## PriceAI 源码对照

2026-10-24 补充核对 PriceAI 提交 `b3092c4487ab96e58dd9d1fb97016ac692ea116e` 的具体实现。此前的参考主要是功能设计，以下记录源码层面的对应及差异。

| 范围 | PriceAI 实现 | 本次落地与边界 |
| --- | --- | --- |
| 商品分类 | [`catalog.ts`](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/src/lib/catalog.ts#L632) 用标准商品目录承接原始报价，优先根据标题重新判断；[`offer-filter-tags.ts`](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/src/lib/offer-filter-tags.ts#L530) 另行处理交付、时长、质保及产品适用的筛选标签 | 本项目按品牌和套餐归类，交付、周期、质保保持独立；采集与后台复用分类规则。未照搬它将不明确的 Gemini、Claude 或 Grok 订阅推断为某个付费等级的规则 |
| 申请与凭据 | [`api-transit-submissions.ts`](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/src/lib/api-transit-submissions.ts) 单独记录待审核申请、去重和限流；[`api-transit-credentials.ts`](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/src/lib/api-transit-credentials.ts#L41) 加密保存测试凭据 | 复用现有中转站后台，前台申请、后台批准上线；凭据复用本项目已有加密服务。未引入测试账号登录采集、密钥预算或多分组凭据管理 |
| 定时探活 | [`probe-api-transit.mjs`](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/scripts/probe-api-transit.mjs#L389) 获取模型列表并发送短生成请求；凭据和参数诊断可不计入可用性，按站点、模型及分组汇总近 7 日样本 | 本次为单站点配置一个协议和模型，每小时采样，展示近 24 小时成功率和 P95；需要非空文本才算成功，模型列表成功不能替代生成成功。尚未实现它的多模型、多分组统计及 OpenAI 参数自动降级 |
| 高级检测 | [`README` 的模型检测服务说明](https://github.com/dimthink/PriceAI/blob/b3092c4487ab96e58dd9d1fb97016ac692ea116e/README.md#L150) 指向独立检测服务，生成协议、能力、来源线路、计费与性能证据报告 | 本次仅实现接口探活与采样统计，未实现模型身份、能力或计费验证报告，不能将探活成功解释为实际模型身份已验证 |

搜索的多词交集、SQL 通配符字面匹配及详情/分页范围一致性，是针对本项目查询链路单独实现和验证的，不宣称与 PriceAI 的搜索算法完全相同。
