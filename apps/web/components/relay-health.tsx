import type { RelayHealth as Health } from "@/lib/types";
import { exactTime, relativeTime } from "@/lib/format";

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

function latency(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}

function sampleTone(status?: string) {
  if (!status) return "empty";
  if (status === "healthy") return "success";
  if (["credential_error", "config_error"].includes(status)) return "diagnostic";
  return "failure";
}

export function RelayHealthSummary({ health }: { health?: Health }) {
  const status = health?.status || "not_checked";
  const rate = health && health.sample_count_24h > 0 ? health.success_rate_24h ?? null : null;
  return (
    <div className="relay-health-summary" aria-label="接口检测摘要">
      <span className="relay-health-status" data-status={status}>{labels[status] || "状态待确认"}</span>
      <p>{rate !== null ? `24h 成功 ${rate}% · ${health?.sample_count_24h} 次` : "暂无有效采样"}</p>
    </div>
  );
}

export function RelayHealthPanel({ health }: { health?: Health }) {
  const status = health?.status || "not_checked";
  const samples = (health?.recent_samples || []).slice(-24);
  const rate = health && health.sample_count_24h > 0 ? health.success_rate_24h ?? null : null;
  const successes = samples.filter((sample) => sample.status === "healthy").length;
  const diagnostics = samples.filter((sample) => ["credential_error", "config_error"].includes(sample.status)).length;
  const sampleLabel = `近 24 小时最近 ${samples.length} 次检测，成功 ${successes} 次、异常 ${samples.length - successes - diagnostics} 次、配置诊断 ${diagnostics} 次；从旧到新，空格表示无样本`;
  return (
    <section className="relay-health-panel" data-status={status} aria-label="接口稳定性">
      <div className="relay-section-heading"><h4>接口稳定性</h4><span className="relay-health-status" data-status={status}>{labels[status] || "状态待确认"}</span></div>
      <p className="relay-health-rate">{rate !== null ? `${rate}%` : "暂无样本"}</p>
      <p className="relay-health-caption" title={health?.diagnostic_count_24h ? `另有 ${health.diagnostic_count_24h} 次配置诊断，不计入成功率` : undefined}>近 24 小时 · {health?.sample_count_24h || 0} 次有效采样</p>
      <div className="relay-samples" role="img" aria-label={sampleLabel}>
        {Array.from({ length: 24 }, (_, index) => {
          const sample = samples[index];
          return <span key={index} data-tone={sampleTone(sample?.status)} aria-hidden="true" title={sample ? `${exactTime(sample.checked_at)} · ${labels[sample.status] || "异常"} · ${latency(sample.latency_ms)}` : "暂无样本"} />;
        })}
      </div>
      <p className="relay-sample-caption">每格一次检测 · 从旧到新</p>
      <dl className="relay-latencies">
        <div><dt>最近耗时</dt><dd>{latency(health?.latency_ms)}</dd></div>
        <div><dt>成功请求 P95</dt><dd>{latency(health?.p95_latency_ms)}</dd></div>
      </dl>
      <p className="relay-health-checked">{health?.checked_at ? <time dateTime={health.checked_at} title={exactTime(health.checked_at)}>{relativeTime(health.checked_at)}检测</time> : "等待首次检测"}</p>
    </section>
  );
}
