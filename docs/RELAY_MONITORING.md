# 中转站检测指标

站长从前台提交官网、Base URL、检测密钥、协议与模型 ID，管理员在后台审核。公开页面只展示审核通过且启用的站点；Base URL、密钥、申请说明和响应正文不公开。每个站点当前检测一个配置的模型，协议标签和模型 ID 来自站长配置，不构成对上游实际模型身份的认证。

启用后每小时最多发起一次短文本模型请求，手动检测共用领取与频率限制。采样采用流式接口，在原来一次请求内采集以下数据，不增加请求频率、不用长提示强制触发缓存。配置变化后只统计新 revision 的记录，历史保存 30 天。

| 页面指标 | 采集与统计口径 |
| --- | --- |
| 对话延迟 | 最近一次真实模型请求总耗时，毫秒；异常记录需要结合状态判断。 |
| 站点 PING | 检测服务器到 API 的 TCP 连接与 TLS 握手耗时，包含连接重试、不含 DNS；不是 ICMP Ping。请求未完成时可能没有该指标。 |
| 可用率 · 7天 | 当前配置近 7 天成功探测 / 有效探测。凭据、权限和配置错误单独作为诊断，不进入分母；限流、超时、无效响应和连接错误计为失败。样本可能未覆盖完整 7 天。 |
| 缓存命中率 · 24h | 近 24 小时返回完整缓存用量的成功采样，缓存读取输入 Token 总和 / 输入 Token 总和。按 Token 加权，排除字段缺失及无效计数，不把缺失当零，也不是请求成功率。 |
| 首 Token P50 · 24h | 近 24 小时成功流式请求，从发起请求到首个非空可见文本的耗时中位数。排除角色、心跳、思考事件；忽略流式参数而返回完整 JSON 的中转站不产生该指标。 |
| 近 60 次检测 | 当前配置近 7 天最新 60 条真实记录，从旧到新。空位放在左侧；不足 60 条保持灰色，不补造成功记录。 |

列表和卡片均直接展示以上指标、当前状态、检测协议和模型，不需要展开。介绍与完整支持模型列表仍可展开。页面每 60 秒刷新读取数据；页面刷新不会发起模型探测，隐藏的浏览器页暂停刷新。最后检测超过两小时显示“检测数据已过期”。

缓存字段按协议解析：

- OpenAI Chat Completions：`usage.prompt_tokens` 已包含缓存输入，读取 `usage.prompt_tokens_details.cached_tokens`；流式请求使用 `stream_options.include_usage=true`，完整 usage 通常在结束前最后一块返回。参考 [OpenAI Docs：流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)。
- Anthropic Messages：总输入为 `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`，缓存读取为 `cache_read_input_tokens`；流式通常从 `message_start.message.usage` 获取，不能让只有输出计数的 `message_delta` 清空它。参考 [Claude 流式消息](https://platform.claude.com/docs/en/build-with-claude/streaming) 与 [缓存计数](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。
- Gemini：`usageMetadata.promptTokenCount` 已包含缓存，读取 `cachedContentTokenCount`；接口为 `streamGenerateContent?alt=sse`，密钥仍放 Header。多次返回的累计 usage 取最新值，不累加。参考 [Gemini API](https://ai.google.dev/api/generate-content)。

短提示可能达不到上游缓存门槛。明确返回缓存计数 0 时显示 0%；没有返回时显示“暂无数据”。这些指标仅代表本站检测服务器、配置模型与短文本请求，不能推断整站真实业务流量的缓存比例或全部模型表现。

v3.9.19 新增 `relay_probe_results` 的 `connect_latency_ms`、`first_token_ms`、`input_tokens`、`cached_input_tokens` 四个可空整数列。已有记录保持 NULL；依次执行 v22 和 `scripts/migrate_relay_probe_metrics_v23.py`，按 [部署流程](QUICK_DEPLOY.md) 先在临时 PostgreSQL 16 双跑演练。`shared_http` 同步重建 API、source-detector、crawler、importer；数据库结构变化需要完整目录发布门禁。
