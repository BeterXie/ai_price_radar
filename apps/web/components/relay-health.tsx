import type { RelayHealth as Health } from "@/lib/types";
import { exactTime, relativeTime } from "@/lib/format";
import { Globe, Lightning } from "@phosphor-icons/react/ssr";

const labels: Record<string, string> = {
  healthy: "请求正常", unhealthy: "接口异常", timeout: "请求超时",
  connection_error: "连接失败", credential_error: "密钥或权限异常",
  config_error: "检测配置异常", rate_limited: "接口限流", invalid_response: "返回内容无效",
  stale: "检测数据已过期", not_checked: "尚未检测", disabled: "未开启监测",
};

export function RelayHealth({ health }: { health?: Health }) {
  return <div className="mt-3 grid gap-1 text-xs leading-6" aria-label="接口检测结果">
    <p className={health?.status === "healthy" ? "text-[color:var(--success)]" : "text-[color:var(--muted)]"}>{labels[health?.status || "not_checked"] || "检测状态待确认"}{health?.checked_at ? ` · ${relativeTime(health.checked_at)}` : ""}</p>
    {health?.probe_model && <p className="break-all text-[color:var(--muted)]">检测模型：{health.probe_model}</p>}
    {health && health.sample_count_24h > 0 ? <p>近 24 小时请求成功率 {health.success_rate_24h}% · {health.sample_count_24h} 次有效采样{health.p95_latency_ms !== null ? ` · P95 ${health.p95_latency_ms} ms` : ""}</p> : <p className="text-[color:var(--muted)]">暂无有效稳定性样本</p>}
    {health?.latency_ms !== null && health?.latency_ms !== undefined && <p className="text-[color:var(--muted)]">最近请求耗时 {health.latency_ms} ms</p>}
  </div>;
}

function latency(value: number | null | undefined, milliseconds = false) {
  if (value === null || value === undefined) return "暂无数据";
  return milliseconds || value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}

function percentage(value: number | null | undefined) {
  return value === null || value === undefined ? "暂无数据" : `${value}%`;
}

function sampleTone(status?: string) {
  if (!status) return "empty";
  if (status === "healthy") return "success";
  if (["credential_error", "config_error"].includes(status)) return "diagnostic";
  return "failure";
}

export function RelayProbeIdentity({ health }: { health?: Health }) {
  const protocols: Record<string, string> = { openai: "OpenAI 兼容", anthropic: "Anthropic", gemini: "Gemini" };
  return <div className="relay-probe-identity">
    {health?.probe_model ? <><span className="relay-protocol" title="站长配置的检测协议；不代表对实际模型身份的认证">{protocols[health.probe_protocol] || "检测接口"}</span><span className="relay-probe-model mono" title={health.probe_model}>{health.probe_model}</span></> : <span className="relay-probe-model">未设置检测模型</span>}
  </div>;
}

export function RelayHealthStatus({ health }: { health?: Health }) {
  const status = health?.status || "not_checked";
  return <span className="relay-health-status" data-status={status}>{labels[status] || "状态待确认"}</span>;
}

export function RelayHealthPanel({ health, now }: { health?: Health; now: number }) {
  const status = health?.status || "not_checked";
  const samples = (health?.recent_samples || []).slice(-60);
  const successes = samples.filter((sample) => sample.status === "healthy").length;
  const diagnostics = samples.filter((sample) => ["credential_error", "config_error"].includes(sample.status)).length;
  const sampleLabel = `近 7 天最近 ${samples.length} 次检测，成功 ${successes} 次、异常 ${samples.length - successes - diagnostics} 次、配置诊断 ${diagnostics} 次；从旧到新，灰色表示无样本`;
  const cacheLabels: Record<string, string> = { healthy: "用量完整", skipped: "首轮失败，未重复请求", usage_missing: "未返回完整缓存用量", insufficient_input: "报告输入过短，未纳入统计" };
  const candyLabel = health?.candy_verdict === "passed" ? "通过" : health?.candy_verdict === "failed" ? "未通过" : "无法判定";
  const cacheSamples = health?.cache_sample_count_24h || 0;
  const cacheMeanSamples = Math.max(0, cacheSamples - 2);
  return (
    <section className="relay-health-panel" data-status={status} aria-label="接口稳定性">
      <dl className="relay-metrics">
        <div data-primary="true" title="最近一次糖果题首次请求，从发起到响应结束的总耗时，包含上游排队、推理和答案传输；失败时结合检测状态判断"><dt><Lightning size={12} aria-hidden />糖果题总耗时</dt><dd>{latency(health?.latency_ms, true)}</dd></div>
        <div data-primary="true" title="检测服务器到 API 的 TCP 连接与 TLS 握手耗时，含连接重试，不含 DNS；不是 ICMP Ping"><dt><Globe size={12} aria-hidden />站点 PING</dt><dd>{latency(health?.connect_latency_ms, true)}</dd></div>
        <div title={`近 7 天 ${health?.sample_count_7d || 0} 次有效探测的成功比例；另有 ${health?.diagnostic_count_7d || 0} 次配置诊断不计入。仅代表当前检测模型。`}><dt>可用率 <span>· 7天</span></dt><dd>{percentage(health?.availability_7d)}</dd></div>
        <div title={`每轮先预热，再重复相同长输入；逐次计算第二次请求的缓存读取 Token / 总输入 Token。近 24 小时各去掉一个最高值和最低值，再取算术平均；极值并列也只各去掉一条，不按 Token 加权。${health?.cache_attempt_count_24h || 0} 次重复请求中 ${cacheSamples} 次用量完整，去极值后 ${cacheMeanSamples} 次参与均值；不足 3 个有效样本不计算。旧短提示、输入不足和缺失用量均不计入。最近：${cacheLabels[health?.cache_probe_status || ""] || labels[health?.cache_probe_status || ""] || "暂无检测"}。`}><dt>重复输入缓存率 <span>· 24h</span></dt><dd>{cacheSamples > 0 && cacheSamples < 3 ? "样本不足" : percentage(health?.cache_hit_rate_24h)}</dd></div>
        <div title={`固定糖果题，首次回答最终整数 21 为通过，其他整数为未通过；超时、截断和无法识别的回答单独计数。只反映该题结果，不认证模型身份或整体能力。最近：${candyLabel}${health?.candy_answer ? `（${health.candy_answer}）` : ""}。`}><dt>糖果测试通过率 <span>· 24h</span></dt><dd>{percentage(health?.candy_pass_rate_24h)}</dd></div>
        <div title={`近 24 小时 ${health?.first_token_sample_count_24h || 0} 次成功流式糖果题请求，从发起到首个答案文本的等待时间中位数，包含上游排队和推理等待。心跳与思考片段不作为首字。题目要求只输出最终整数，因此首字可能接近总耗时。`}><dt>糖果题首字 P50 <span>· 24h</span></dt><dd>{latency(health?.first_token_p50_ms)}</dd></div>
      </dl>
      <p className="relay-benchmark-caption">糖果：{health?.candy_passed_count_24h || 0}/{health?.candy_sample_count_24h || 0} 次通过 · {health?.candy_inconclusive_count_24h || 0} 次无法判定；缓存：{cacheSamples}/{health?.cache_attempt_count_24h || 0} 次用量完整 · {cacheSamples >= 3 ? `去极值后 ${cacheMeanSamples} 次均值` : "满 3 次后计算去极值均值"}</p>
      <div className="relay-history-heading"><span>近 60 次检测 <span>· {samples.length} 次记录</span></span><span>{health?.checked_at ? <time dateTime={health.checked_at} title={exactTime(health.checked_at)}>{relativeTime(health.checked_at, now)}检测</time> : "等待首次检测"}</span></div>
      <div className="relay-samples" role="img" aria-label={sampleLabel}>
        {Array.from({ length: 60 }, (_, index) => {
          const sample = samples[index - (60 - samples.length)];
          return <span key={index} data-tone={sampleTone(sample?.status)} aria-hidden="true" title={sample ? `${exactTime(sample.checked_at)} · ${labels[sample.status] || "异常"} · ${latency(sample.latency_ms)}` : "暂无样本"} />;
        })}
      </div>
      <p className="relay-sample-caption"><span>较早</span><span>每格一次 · 最近</span></p>
    </section>
  );
}
