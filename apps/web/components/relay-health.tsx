import type { RelayHealth as Health } from "@/lib/types";
import { relativeTime } from "@/lib/format";

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
