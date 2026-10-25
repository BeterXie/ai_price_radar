# v3.9.24 中转站模型、分组倍率同步与探测等待时间

Tosky.io 在生产服务器复测时，TCP/TLS 连接约 0.2 秒完成，但等待响应头约 15.8 秒，随后返回 HTTP 200 和完整模型回复。原探测器的 15 秒等待上限会将这类响应判为超时。

模型探测的单次等待上限由 15 秒调整为 30 秒，总时限由 20 秒调整为 45 秒，继续限制响应体大小并要求完整有效的模型回复。历史失败记录和可用率统计保留，不对其他 HTTP 客户端的超时配置作修改。

MX-API 两轮生产复测均返回完整回复，总耗时约 3.3–3.6 秒；历史失败未记录阶段，无法确认当次超时原因。

新增密钥授权的模型目录同步，复用公开 HTTPS 校验、DNS 固定和密钥头白名单。支持 OpenAI、Anthropic 与 Gemini 的模型列表及后两者的分页，每小时在独立任务中自动同步，后台也可以手动同步。同步不阻塞健康检测。仅保存模型 ID、名称、归属、介绍、上下文或输入输出上限及能力等明确返回的字段，不猜测价格或介绍。目录不代表逐个模型均已完成调用测试。

每站支持分组选择、分组倍率与当前生效倍率展示，优先通过同一 Base URL 的 `/v1/sub2api/billing` 读取密钥分组；接口不支持时回退公开 New API `/api/pricing` 的 `group_ratio` 与 `enable_groups`。参考 PriceAI 的公开采集与密钥实测分离方式，公开分组不视为当前密钥的调用授权；接口不提供分组名称或模型范围时明确标注，不猜测默认倍率。申请页和后台支持人工补录分组、倍率与模型范围，相同标识的人工资料优先于自动缓存。

生产只读实测：LLMPort、Tosky、MX-API 的当前密钥分组倍率分别为 0.12×、0.18×、0.15×；AllTokens 返回 GPT(企业级) 0.25×、GPT（PRO）0.16×、GPT(官Key) 0.30×。接口未返回这几组的模型映射，不能据此宣称每组均支持整份密钥模型清单。以上为调研时返回值，上线后以定时同步为准。

前台保持紧凑列表和卡片布局，默认显示模型数量，展开后可以搜索模型。同步失败保留上次成功清单并显示时间；更改 Base URL、密钥、协议或检测模型会清除旧清单，过期配置的在途结果不会覆盖新配置。

修复站点图标偶发缺失：识别网页内嵌的有界 base64 栅格图标，HTML 读取上限调整为 1 MiB，图标仍限定 256 KiB，继续拒绝 SVG、HTML 和非公开地址。成功图标持久保存在数据库，每日刷新，源站超时或并发繁忙时保留旧图标；API 重启后可直接读取已保存图标。前端检查已完成的缓存图片，避免图片在 hydration 前加载完成而始终透明；暂时失败会延后重试并保留首字占位。

接口来源：[OpenAI Models](https://developers.openai.com/api/reference/resources/models/methods/list)、[Claude Models](https://platform.claude.com/docs/en/api/models/list)、[Gemini Models](https://ai.google.dev/api/models)。具体清单以各中转站的真实返回为准。

实现参考：[PriceAI 采集流程](https://github.com/dimthink/PriceAI/blob/main/public-docs/api-transit-model-collection-flow.md)、[Sub2API Key Billing](https://github.com/Wei-Shaw/sub2api/blob/main/backend/internal/handler/gateway_key_billing.go)。分组选择只切换展示资料，健康数据仍来自已配置的检测密钥。

部署前执行 `scripts/migrate_relay_model_catalog_v24.py`，仅增加空模型目录缓存、人工分组和持久图标 JSON 字段，不回填历史数据。按 `docs/QUICK_DEPLOY.md` 重建 API、Web、Importer、Source Detector 和 Crawler，并在临时 PostgreSQL 16 重复演练迁移后完成完整多来源发布及验收。
