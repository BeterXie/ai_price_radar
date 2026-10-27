# 中转站检测指标

站长从前台提交官网、Base URL、检测密钥、协议与模型 ID，管理员在后台审核。公开页面只展示审核通过且启用的站点；Base URL、密钥、申请说明和响应正文不公开。每个站点当前检测一个配置的模型，协议标签和模型 ID 来自站长配置，不构成对上游实际模型身份的认证。

启用后每小时最多运行一轮测试，手动检测共用领取与频率限制。每轮先用固定长输入回答糖果题，首次请求成功后再重复完全相同的输入测缓存；不附带上一次答案。采样采用流式接口，首轮采集糖果结果和耗时，第二轮采集缓存用量。配置变化后只统计新 revision 的记录，历史保存 30 天。

| 页面指标 | 采集与统计口径 |
| --- | --- |
| 糖果题总耗时 | 最近一次首轮糖果题请求总耗时，毫秒；异常记录需要结合状态判断。 |
| 站点 PING | 检测服务器到 API 的 TCP 连接与 TLS 握手耗时，包含连接重试、不含 DNS；不是 ICMP Ping。请求未完成时可能没有该指标。 |
| 可用率 · 7天 | 当前配置近 7 天成功探测 / 有效探测。凭据、权限和配置错误单独作为诊断，不进入分母；限流、超时、无效响应和连接错误计为失败。样本可能未覆盖完整 7 天。 |
| 重复输入缓存率 · 24h | 对近 24 小时有效第二轮请求逐次计算缓存读取 Token / 总输入 Token，各去掉一个最高值和最低值，再取剩余比例的算术平均，保留两位小数。极值并列也只各去掉一条；不足 3 个有效样本时返回 null，页面区分“样本不足”和“暂无数据”。原始记录与去极值前的样本计数保留，不按 Token 加权。 |
| 糖果测试通过率 · 24h | 首轮最终整数 21 为通过，其他整数为未通过；超时、截断和无法识别单列为无法判定。只描述该题结果，不认证整体能力或模型身份。 |
| 糖果题首字 P50 · 24h | 近 24 小时成功首轮流式请求，从发起请求到首个非空答案文本的耗时中位数，包含推理等待。排除角色、心跳、思考事件；忽略流式参数而返回完整 JSON 的中转站不产生该指标。只输出一个整数时，首字可能接近总耗时。 |
| 近 60 次检测 | 当前配置近 7 天最新 60 条真实记录，从旧到新。空位放在左侧；不足 60 条保持灰色，不补造成功记录。 |

列表和卡片均直接展示以上指标、当前状态、检测协议和模型，不需要展开。介绍与完整支持模型列表仍可展开。页面每 60 秒刷新读取数据；页面刷新不会发起模型探测，隐藏的浏览器页暂停刷新。最后检测超过两小时显示“检测数据已过期”。

缓存字段按协议解析：

- OpenAI Chat Completions：`usage.prompt_tokens` 已包含缓存输入，读取 `usage.prompt_tokens_details.cached_tokens`；流式请求使用 `stream_options.include_usage=true`，完整 usage 通常在结束前最后一块返回。参考 [OpenAI Docs：流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)。
- Anthropic Messages：总输入为 `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`，缓存读取为 `cache_read_input_tokens`；流式通常从 `message_start.message.usage` 获取，不能让只有输出计数的 `message_delta` 清空它。参考 [Claude 流式消息](https://platform.claude.com/docs/en/build-with-claude/streaming) 与 [缓存计数](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。
- Gemini：`usageMetadata.promptTokenCount` 已包含缓存，读取 `cachedContentTokenCount`；接口为 `streamGenerateContent?alt=sse`，密钥仍放 Header。多次返回的累计 usage 取最新值，不累加。参考 [Gemini API](https://ai.google.dev/api/generate-content)。

缓存统计只纳入当前基准版本中首轮和第二轮均成功、第二轮报告至少 1,024 个输入 Token 且缓存计数完整有效的样本；旧短提示、缺失和无效用量不计入。明确返回缓存计数 0 的样本参与排序，不能把缺失当零或把所有零值删除。页面显示去极值前完整用量的样本数和去极值后参与均值的次数。该值仅代表固定测试的去极值均值，与后台真实业务流量的 Token 加权缓存率口径不同，不能推断整站或全部模型表现。

部分 Sub2API 中转站（如 AllTokens）的 Chat Completions 转换层会省略全零的缓存明细，但同一检测密钥的 `GET /v1/usage` 仍返回用量计数。OpenAI 兼容探活会先读取该接口的 `usage.total` 作为基线；本次成功响应缺少缓存计数时，再读取一次用量进行核对，响应自带完整缓存计数时优先使用响应。只保留请求数、普通输入、缓存读取和缓存创建计数；不保存余额、费用、用户资料或完整响应。

补充采集只有在累计请求数恰好增加 1、各输入计数没有倒退，且三类输入增量之和等于本次模型响应的输入 Token 时才有效。先确认预热请求已入账，才允许用第二次请求的账单差额补充缓存读数，避免延迟的预热账单被误算到第二轮。有效的第二轮计数写入原始样本，查询时再按近 24 小时去极值平均；不会把今日或累计用量当作近 24 小时。异步记账尚未更新时最多追加一次延迟 250ms 的读取。接口不支持、超时、字段缺失、计数重置、并发调用或输入数不匹配均保持缓存未知，不改变探活状态。补充请求各自限制为 5 秒、128 KiB，不计入糖果题总耗时或首字耗时，也不增加模型请求次数。

v3.9.19 新增 `relay_probe_results` 的 `connect_latency_ms`、`first_token_ms`、`input_tokens`、`cached_input_tokens` 四个可空整数列。已有记录保持 NULL；依次执行 v22 和 `scripts/migrate_relay_probe_metrics_v23.py`，按 [部署流程](QUICK_DEPLOY.md) 先在临时 PostgreSQL 16 双跑演练。`shared_http` 同步重建 API、source-detector、crawler、importer；数据库结构变化需要完整目录发布门禁。
