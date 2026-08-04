export const CANDIDATE_STATUS_LABELS: Record<string, string> = {
  discovered: "已发现",
  queued: "排队中",
  detecting: "检测中",
  detected: "已检测",
  no_match: "无 AI 商品",
  validation_failed: "验证失败",
  pending_review: "待审核",
  auto_approved: "自动批准",
  promoted: "已促进",
  rejected: "已拒绝",
  needs_re_review: "需复审",
  disabled: "已禁用",
};

export const RUN_STATUS_LABELS: Record<string, string> = {
  running: "运行中",
  succeeded: "成功",
  partial: "部分失败",
  failed: "失败",
};

export function candidateStatusLabel(status: string): string {
  return CANDIDATE_STATUS_LABELS[status] || status;
}

export function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] || status;
}

export interface DiscoveryRunMetrics {
  discovered_raw_count?: number;
  normalized_count?: number;
  duplicate_count?: number;
  new_candidate_count?: number;
  detected_count?: number;
  ai_matched_count?: number;
  auto_approved_count?: number;
  pending_review_count?: number;
  validation_failed_count?: number;
  promoted_intake_count?: number;
}

export interface DiscoveryFunnel {
  discovered_raw: number;
  normalized: number;
  duplicates: number;
  new_candidates: number;
  detected: number;
  ai_matched: number;
  auto_approved: number;
  pending_review: number;
  validation_failed: number;
  promoted: number;
}

export function funnelFromRuns(runs: DiscoveryRunMetrics[]): DiscoveryFunnel {
  // 口径：只汇总运行记录里已上报的首次验证转化（检测/AI/审批/失败/促进）。
  const total: DiscoveryFunnel = {
    discovered_raw: 0,
    normalized: 0,
    duplicates: 0,
    new_candidates: 0,
    detected: 0,
    ai_matched: 0,
    auto_approved: 0,
    pending_review: 0,
    validation_failed: 0,
    promoted: 0,
  };
  for (const run of runs || []) {
    total.discovered_raw += run.discovered_raw_count || 0;
    total.normalized += run.normalized_count || 0;
    total.duplicates += run.duplicate_count || 0;
    total.new_candidates += run.new_candidate_count || 0;
    total.detected += run.detected_count || 0;
    total.ai_matched += run.ai_matched_count || 0;
    total.auto_approved += run.auto_approved_count || 0;
    total.pending_review += run.pending_review_count || 0;
    total.validation_failed += run.validation_failed_count || 0;
    total.promoted += run.promoted_intake_count || 0;
  }
  return total;
}

export interface DiscoveryFilters {
  status?: string;
  detected_platform?: string;
  discovered_by?: string;
  ai_hit?: boolean;
  limit?: number;
}

export function candidateQuery(filters: DiscoveryFilters): string {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.detected_platform) params.set("detected_platform", filters.detected_platform);
  if (filters.discovered_by) params.set("discovered_by", filters.discovered_by);
  if (filters.ai_hit) params.set("ai_hit", "true");
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}
