"use client";

import { useEffect, useState } from "react";
import { ArrowClockwise, Check, EyeSlash, X } from "@phosphor-icons/react";
import { candidateQuery, candidateStatusLabel, funnelFromRuns, runStatusLabel } from "@/lib/source-discovery";

type Run = {
  id: number;
  trigger: string;
  adapters: string[];
  status: string;
  started_at: string | null;
  finished_at: string | null;
  discovered_raw_count: number;
  normalized_count: number;
  duplicate_count: number;
  new_candidate_count: number;
  detected_count: number;
  ai_matched_count: number;
  auto_approved_count: number;
  pending_review_count: number;
  validation_failed_count: number;
  promoted_intake_count: number;
  adapter_stats: Record<string, number>;
  failure_stats: Record<string, number>;
  note: string;
};

type Candidate = {
  id: number;
  candidate_key: string;
  canonical_url: string;
  platform_hint: string;
  detected_platform: string;
  detected_source_url: string;
  discovered_by: string;
  discovery_sources: string[];
  ai_product_count: number;
  total_product_count: number;
  status: string;
  failure_reason: string;
  decision_note: string;
  attempt_count: number;
  last_seen_at: string;
  next_verify_at: string | null;
  promoted_intake_id: number | null;
  sample_products: { name: string; url: string }[];
};

const PLATFORM_LABELS: Record<string, string> = {
  unknown: "未识别",
  ldxp: "链动小铺",
  dujiao_next: "Dujiao-Next",
  merchant_json: "商家 Feed",
  woocommerce: "WooCommerce",
  schema_org: "Schema.org",
  other: "其他",
};

export function SourceDiscoveryPanel({ apiBase, headers }: { apiBase: string; headers: Record<string, string> }) {
  const adminKey = headers["X-Admin-Key"];
  const [runs, setRuns] = useState<Run[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    const query = candidateQuery({ status: statusFilter || undefined, detected_platform: platformFilter || undefined, limit: 200 });
    const [runsResponse, candidatesResponse] = await Promise.all([
      fetch(`${apiBase}/api/v1/admin/source-discovery/runs?limit=100`, { headers }),
      fetch(`${apiBase}/api/v1/admin/source-candidates${query}`, { headers }),
    ]);
    if (!runsResponse.ok || !candidatesResponse.ok) {
      setError("来源发现数据加载失败，请确认管理密钥和 API 可用。");
      return;
    }
    setRuns(await runsResponse.json());
    setCandidates(await candidatesResponse.json());
  }

  useEffect(() => {
    if (adminKey) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adminKey, statusFilter, platformFilter]);

  async function act(candidateId: number, action: "retry" | "reject" | "disable" | "promote") {
    const reason =
      action === "reject" || action === "disable"
        ? window.prompt(action === "reject" ? "拒绝原因" : "禁用原因", "") || ""
        : "";
    if ((action === "reject" || action === "disable") && !reason.trim()) {
      setError("请填写原因后再操作。");
      return;
    }
    const response = await fetch(`${apiBase}/api/v1/admin/source-candidates/${candidateId}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ reason }),
    });
    if (response.ok) await load();
    else setError("候选状态更新失败，请刷新后重试。");
  }

  const funnel = funnelFromRuns(runs);
  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">来源发现引擎</h2>
        <button onClick={load} className="tactile rounded-[10px] bg-[color:var(--ink)] px-4 py-2 text-sm text-white">
          刷新发现数据
        </button>
      </div>
      {error && <p className="rounded-[10px] bg-[#f2d8d2] p-4 text-[color:var(--danger)]">{error}</p>}

      <div className="data-table-frame grid gap-px overflow-hidden border hairline bg-[color:var(--line)] sm:grid-cols-3 lg:grid-cols-5">
        {[
          ["发现原始 URL", funnel.discovered_raw],
          ["归一化候选", funnel.normalized],
          ["新增候选", funnel.new_candidates],
          ["AI 命中", funnel.ai_matched],
          ["已转入收录", funnel.promoted],
        ].map(([label, value]) => (
          <div key={String(label)} className="bg-[color:var(--panel)] p-4">
            <p className="mono text-xs text-black/40">{label}</p>
            <p className="mt-2 text-2xl font-semibold">{value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-black/50">
        漏斗口径：统计各运行“首次新增候选”的首次验证转化（检测 / AI 命中 / 自动批准 / 待审 / 失败 / 转入收录）。全量历史累计不在此口径中。
      </p>

      <div className="data-table-frame overflow-hidden border hairline bg-[color:var(--panel)]">
        <div className="border-b hairline px-5 py-4 font-semibold">发现运行记录</div>
        <div className="divide-y divide-[color:var(--line)]">
          {runs.length === 0 && <p className="px-5 py-4 text-sm text-black/50">还没有发现运行记录。</p>}
          {runs.map((run) => (
            <div key={run.id} className="grid gap-2 px-5 py-4 lg:grid-cols-[auto_1fr_auto] lg:items-center">
              <span className="mono text-xs text-black/40">#{run.id} · {run.trigger}</span>
              <div>
                <p className="text-sm">
                  {run.adapters.join("、")} · <span className="status-pill status-info">{runStatusLabel(run.status)}</span>
                </p>
                <p className="mt-1 text-xs text-black/50">
                  原始 {run.discovered_raw_count} / 归一化 {run.normalized_count} / 重复 {run.duplicate_count} / 新增 {run.new_candidate_count} / 检测 {run.detected_count} / AI 命中 {run.ai_matched_count} / 自动批准 {run.auto_approved_count} / 待审 {run.pending_review_count} / 失败 {run.validation_failed_count} / 转入收录 {run.promoted_intake_count}
                </p>
                {run.finished_at && <p className="mt-1 mono text-[11px] text-black/40">开始 {run.started_at} · 结束 {run.finished_at}</p>}
              </div>
              <div className="text-right text-xs text-black/50">
                {Object.entries(run.adapter_stats || {}).map(([adapter, count]) => `${adapter}:${count}`).join(" · ") || "无适配器统计"}
                {Object.keys(run.failure_stats || {}).length > 0 && <p className="mt-1 text-[color:var(--danger)]">失败：{Object.entries(run.failure_stats).map(([kind, count]) => `${kind}:${count}`).join(" · ")}</p>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="data-table-frame overflow-hidden border hairline bg-[color:var(--panel)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b hairline px-5 py-4">
          <div className="font-semibold">来源候选池</div>
          <div className="flex flex-wrap gap-2">
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm">
              <option value="">全部状态</option>
              {Object.entries(candidateStatusLabels()).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)} className="rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm">
              <option value="">全部平台</option>
              {Object.entries(PLATFORM_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>
        <div className="divide-y divide-[color:var(--line)]">
          {candidates.length === 0 && <p className="px-5 py-4 text-sm text-black/50">没有符合条件的候选。</p>}
          {candidates.map((candidate) => (
            <div key={candidate.id} className="px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-all text-sm font-medium">{candidate.canonical_url}</p>
                  <p className="mono mt-1 text-xs text-black/40">
                    #{candidate.id} · {PLATFORM_LABELS[candidate.detected_platform] || candidate.detected_platform} · {candidateStatusLabel(candidate.status)} · AI {candidate.ai_product_count}/{candidate.total_product_count} · 尝试 {candidate.attempt_count}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => setExpandedId(expandedId === candidate.id ? null : candidate.id)} className="tactile rounded-[10px] border hairline px-3 py-2 text-sm">
                    {expandedId === candidate.id ? "收起" : "详情"}
                  </button>
                  {["validation_failed", "no_match", "needs_re_review", "rejected", "disabled"].includes(candidate.status) && (
                    <button onClick={() => act(candidate.id, "retry")} className="tactile flex items-center gap-1 rounded-[10px] border hairline px-3 py-2 text-sm"><ArrowClockwise size={15} />重试</button>
                  )}
                  {["pending_review", "auto_approved", "detected"].includes(candidate.status) && (
                    <button onClick={() => act(candidate.id, "promote")} className="tactile flex items-center gap-1 rounded-[10px] bg-[color:var(--ink)] px-3 py-2 text-sm text-white"><Check size={15} />转入收录</button>
                  )}
                  {!["rejected", "disabled", "detecting", "promoted"].includes(candidate.status) && (
                    <>
                      <button onClick={() => act(candidate.id, "reject")} className="tactile flex items-center gap-1 rounded-[10px] border hairline px-3 py-2 text-sm"><X size={15} />拒绝</button>
                      <button onClick={() => act(candidate.id, "disable")} className="tactile flex items-center gap-1 rounded-[10px] border hairline px-3 py-2 text-sm"><EyeSlash size={15} />禁用</button>
                    </>
                  )}
                </div>
              </div>
              {expandedId === candidate.id && (
                <div className="mt-4 grid gap-3 rounded-[9px] bg-[color:var(--info-soft)] p-4 text-sm">
                  <p className="break-all">发现来源：{candidate.discovery_sources.join("、") || "未知"}</p>
                  <p className="break-all">候选键：{candidate.candidate_key}</p>
                  <p className="break-all">检测后来源：{candidate.detected_source_url || "未检测"}</p>
                  {candidate.failure_reason && <p className="rounded-[8px] bg-[#f2d8d2] px-3 py-2 text-[color:var(--danger)]">失败原因：{candidate.failure_reason}</p>}
                  {candidate.decision_note && <p className="whitespace-pre-line text-black/65">决策备注：{candidate.decision_note}</p>}
                  {candidate.promoted_intake_id && <p>已转入收录申请 #{candidate.promoted_intake_id}</p>}
                  {candidate.sample_products.length > 0 && (
                    <div>
                      <p className="mb-1 font-medium">商品样本</p>
                      {candidate.sample_products.map((sample) => <p key={sample.url} className="break-all text-xs"><a className="underline" href={sample.url} target="_blank" rel="noreferrer">{sample.name}</a></p>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function candidateStatusLabels() {
  return {
    discovered: "已发现",
    queued: "排队中",
    detecting: "检测中",
    no_match: "无 AI 商品",
    validation_failed: "验证失败",
    pending_review: "待审核",
    auto_approved: "自动批准",
    promoted: "已转入收录",
    rejected: "已拒绝",
    needs_re_review: "需复审",
    disabled: "已禁用",
  };
}
