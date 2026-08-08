"use client";

import { useEffect, useState } from "react";
import { ArrowClockwise, Check, Eye, EyeSlash, Key, X } from "@phosphor-icons/react";
import { money } from "@/lib/format";
import { SourceDiscoveryPanel } from "@/components/source-discovery-panel";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const PRODUCT_OPTIONS = [
  "chatgpt-account",
  "chatgpt-plus",
  "chatgpt-go",
  "chatgpt-k12",
  "chatgpt-pro-5x",
  "chatgpt-pro-20x",
  "chatgpt-pro",
  "openai-api-credit",
  "chatgpt-access-service",
  "codex-access",
  "claude-pro",
  "claude-account",
  "claude-api-access",
  "gemini-advanced",
  "gemini-account",
  "gemini-api-access",
  "grok-super",
  "grok-account",
  "grok-api-access",
  "x-premium-basic",
  "x-premium",
  "x-premium-plus",
];

type Stats = {
  shops: number;
  products: number;
  offers: number;
  public_offers: number;
  open_corrections: number;
  pending_source_intakes: number;
  open_reports: number;
  last_scan_at: string | null;
};

type AdminOffer = {
  id: number;
  shop: string;
  title: string;
  product_slug: string | null;
  price: string | null;
  currency: string;
  stock_status: string;
  approved: boolean;
  active: boolean;
};

type Report = {
  id: number;
  offer_id: number | null;
  kind: string;
  message: string;
  contact: string;
  status: string;
  public_summary: string;
  merchant_response: string;
  resolved_at: string | null;
  created_at: string;
};

type SourceType = "unknown" | "ldxp" | "dujiao_next" | "merchant_json" | "woocommerce" | "schema_org" | "other";

type SourceIntake = {
  id: number;
  source_type: SourceType;
  source_url: string;
  shop_name: string;
  contact_email: string;
  note: string;
  origin: string;
  status: string;
  decision_note: string;
  failure_reason: string;
  attempt_count: number;
  product_count: number;
  approved_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  email_status: Record<string, string>;
};

const REPORT_KIND_LABELS: Record<string, string> = {
  correction: "报价纠错",
  unavailable: "无法购买",
  fraud_concern: "风险反馈",
  other: "其他反馈",
};

export function AdminPanel() {
  const [key, setKey] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [offers, setOffers] = useState<AdminOffer[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [intakes, setIntakes] = useState<SourceIntake[]>([]);
  const [targetIntakeId, setTargetIntakeId] = useState<number | null>(null);
  const [reportDrafts, setReportDrafts] = useState<Record<number, { public_summary: string; merchant_response: string }>>({});
  const [intakeReasons, setIntakeReasons] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const headers = { "X-Admin-Key": key };

  useEffect(() => {
    const intakeId = Number(new URLSearchParams(window.location.search).get("intake"));
    if (Number.isInteger(intakeId) && intakeId > 0) setTargetIntakeId(intakeId);
  }, []);

  useEffect(() => {
    if (targetIntakeId === null || !intakes.some((intake) => intake.id === targetIntakeId)) return;
    document.getElementById(`source-intake-${targetIntakeId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [intakes, targetIntakeId]);

  async function load() {
    setError("");
    const [statsResponse, offersResponse, reportsResponse, intakesResponse] = await Promise.all([
      fetch(`${API}/api/v1/admin/stats`, { headers }),
      fetch(`${API}/api/v1/admin/offers?limit=50`, { headers }),
      fetch(`${API}/api/v1/admin/reports?status=open`, { headers }),
      fetch(`${API}/api/v1/admin/source-intakes`, { headers }),
    ]);
    if (!statsResponse.ok || !offersResponse.ok || !reportsResponse.ok || !intakesResponse.ok) {
      setError("管理密钥无效，或 API 无法访问。");
      return;
    }
    setStats(await statsResponse.json());
    setOffers(await offersResponse.json());
    const loadedReports = await reportsResponse.json() as Report[];
    setReports(loadedReports);
    setReportDrafts(Object.fromEntries(loadedReports.map((report) => [report.id, { public_summary: report.public_summary || "", merchant_response: report.merchant_response || "" }])));
    const loadedIntakes = await intakesResponse.json() as SourceIntake[];
    setIntakes(loadedIntakes);
    setIntakeReasons(Object.fromEntries(loadedIntakes.map((intake) => [intake.id, intake.decision_note || ""])));
  }

  async function patchOffer(offerId: number, body: Record<string, unknown>) {
    const response = await fetch(`${API}/api/v1/admin/offers/${offerId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
    if (response.ok) await load();
  }

  async function reclassify() {
    const response = await fetch(`${API}/api/v1/admin/reclassify`, {
      method: "POST",
      headers,
    });
    if (response.ok) await load();
  }

  async function resolveReport(reportId: number, status: "resolved" | "rejected") {
    const draft = reportDrafts[reportId] || { public_summary: "", merchant_response: "" };
    if (status === "resolved" && !draft.public_summary.trim()) {
      setError("发布已处理记录前，请填写不含联系方式和私密内容的公开摘要。");
      return;
    }
    const response = await fetch(`${API}/api/v1/admin/reports/${reportId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ status, public_summary: draft.public_summary.trim(), merchant_response: draft.merchant_response.trim() }),
    });
    if (response.ok) await load();
  }

  async function updateIntake(intakeId: number, action: "approve" | "reject" | "retry") {
    const body = action === "reject" ? { reason: (intakeReasons[intakeId] || "").trim() } : undefined;
    if (action === "reject" && !body?.reason) {
      setError("驳回收录申请前，请填写原因。");
      return;
    }
    const response = await fetch(`${API}/api/v1/admin/source-intakes/${intakeId}/${action}`, {
      method: "POST",
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (response.ok) await load();
    else setError("收录申请状态更新失败，请刷新后重试。");
  }

  async function retryFailedIntakeNotifications(intakeId: number) {
    const response = await fetch(`${API}/api/v1/admin/source-intakes/${intakeId}/notifications/retry`, {
      method: "POST",
      headers,
    });
    if (response.ok) await load();
    else setError("失败邮件重发排队失败，请刷新后重试。");
  }

  const intakeStatusLabels: Record<string, string> = {
    submitted: "等待安全检测",
    detecting: "安全检测中",
    pending_review: "待初审",
    approved: "已批准，等待同步",
    queued: "等待读取",
    validating: "正在读取",
    validated: "读取成功，等待发布",
    onboarded: "已收录，等待发布",
    published: "已发布",
    needs_re_review: "需要重新审核",
    disabled: "已停用",
    rejected: "已驳回",
    no_products: "未发现目标商品",
    validation_failed: "验证失败",
  };
  const sourceTypeLabels: Record<string, string> = {
    unknown: "待识别来源",
    ldxp: "链动小铺",
    dujiao_next: "Dujiao-Next",
    woocommerce: "WooCommerce",
    schema_org: "Schema.org 独立站",
    merchant_json: "商家 JSON Feed",
    other: "其他独立站",
  };

  function emailStatusLabel(status: string) {
    return status === "sent" ? "已发送" : status === "failed" ? "发送失败" : status === "sending" ? "发送中" : "待发送";
  }

  return (
    <div className="space-y-8">
      <section className="surface-panel grid gap-4 p-5 md:grid-cols-[1fr_auto_auto] md:items-end">
        <label className="text-sm font-medium">
          管理密钥
          <span className="mt-2 flex min-h-11 items-center gap-2 rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 focus-within:border-[color:var(--focus)]">
            <Key size={18} />
            <input
              value={key}
              onChange={(event) => setKey(event.target.value)}
              type="password"
              className="w-full bg-transparent py-3 outline-none"
            />
          </span>
        </label>
        <button onClick={load} className="button-primary tactile">
          验证并加载
        </button>
        <button onClick={reclassify} className="button-secondary tactile">
          <ArrowClockwise size={17} />重新分类
        </button>
      </section>

      {error && <p role="alert" className="rounded-[10px] border border-[color:var(--danger)]/25 bg-[color:var(--danger-soft)] p-4 text-[color:var(--danger)]">{error}</p>}

      {stats && (
        <section className="data-strip sm:grid-cols-2 lg:grid-cols-6">
          {[
            ["店铺", stats.shops],
            ["标准产品", stats.products],
            ["全部报价", stats.offers],
            ["公开报价", stats.public_offers],
            ["待处理纠错", stats.open_corrections],
            ["待初审收录申请", stats.pending_source_intakes],
          ].map(([label, value]) => (
            <div key={String(label)} className="data-cell">
              <p className="data-label">{label}</p>
              <p className="data-value">{value}</p>
            </div>
          ))}
        </section>
      )}

      {intakes.length > 0 && (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 font-semibold">店铺收录申请</div>
          <div className="divide-y divide-[color:var(--line)]">
            {intakes.map((intake) => (
              <div id={`source-intake-${intake.id}`} key={intake.id} className={`scroll-mt-6 grid gap-5 px-5 py-5 xl:grid-cols-[1fr_auto] xl:items-start ${targetIntakeId === intake.id ? "bg-[color:var(--brand-soft)]" : ""}`}>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="mono text-xs text-black/40">#{intake.id} · {sourceTypeLabels[intake.source_type] || intake.source_type}</p>
                    <span className="status-pill status-info">{intakeStatusLabels[intake.status] || intake.status}</span>
                  </div>
                  <p className="mt-2 break-all text-sm font-medium">{intake.shop_name || "未填写来源名称"}</p>
                  <p className="mt-1 break-all text-xs leading-5 text-black/55">{intake.source_url}</p>
                  <p className="mt-2 text-xs text-black/50">联系邮箱：{intake.contact_email} · 商品数：{intake.product_count} · 重试次数：{intake.attempt_count}</p>
                  {intake.note && <p className="mt-2 whitespace-pre-line text-sm leading-6 text-black/65">申请说明：{intake.note}</p>}
                  {intake.source_type === "other" && intake.status === "pending_review" && <p className="mt-2 text-sm leading-6 text-black/65">其他独立站仅支持管理员人工接入，不会进入自动验证或发布队列。</p>}
                  {["merchant_json", "woocommerce", "schema_org"].includes(intake.source_type) && intake.status === "approved" && <p className="mt-2 text-sm leading-6 text-black/65">等待目录发布流程安全拉取并分类商品；成功进入完整快照后才会公开。</p>}
                  {intake.failure_reason && <p className="mt-2 rounded-[10px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm leading-6 text-[color:var(--danger)]">失败原因：{intake.failure_reason}</p>}
                  {Object.keys(intake.email_status).length > 0 && <p className="mt-3 text-xs text-black/50">邮件状态：{Object.entries(intake.email_status).map(([event, mailStatus]) => `${event} ${emailStatusLabel(mailStatus)}`).join(" · ")}</p>}
                  {intake.status === "pending_review" && <label className="mt-4 block text-xs font-medium text-black/55">驳回原因<input value={intakeReasons[intake.id] || ""} onChange={(event) => setIntakeReasons((current) => ({ ...current, [intake.id]: event.target.value }))} maxLength={500} placeholder="仅在驳回时必填" className="field mt-1.5 text-sm" /></label>}
                </div>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  {intake.status === "pending_review" && <>{intake.source_type !== "other" && <button onClick={() => updateIntake(intake.id, "approve")} className="button-primary tactile"><Check size={16} />{intake.source_type === "ldxp" ? "批准并验证" : "批准并加入发布队列"}</button>}<button onClick={() => updateIntake(intake.id, "reject")} className="button-danger tactile"><X size={16} />驳回</button></>}
                  {intake.source_type !== "other" && (intake.status === "no_products" || intake.status === "validation_failed") && <button onClick={() => updateIntake(intake.id, "retry")} className="tactile rounded-[10px] border hairline px-3 py-2 text-sm"><ArrowClockwise size={16} className="mr-1 inline" />重新验证</button>}
                  {Object.values(intake.email_status).some((mailStatus) => mailStatus === "failed") && <button onClick={() => retryFailedIntakeNotifications(intake.id)} className="tactile rounded-[10px] border border-[color:var(--danger)] px-3 py-2 text-sm text-[color:var(--danger)]"><ArrowClockwise size={16} className="mr-1 inline" />重发失败邮件</button>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {key && (
        <SourceDiscoveryPanel apiBase={API} headers={headers} />
      )}

      {reports.length > 0 && (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 font-semibold">纠错与风险反馈</div>
          <div className="divide-y divide-[color:var(--line)]">
            {reports.map((report) => (
              <div key={report.id} className="grid gap-4 px-5 py-4 md:grid-cols-[1fr_auto] md:items-center">
                <div>
                  <p className="mono text-xs text-black/40">{REPORT_KIND_LABELS[report.kind] || report.kind}{report.offer_id ? ` / 报价 #${report.offer_id}` : ""}</p>
                  <p className="mt-2 whitespace-pre-line text-sm leading-6">{report.message}</p>
                  {report.contact && <p className="mt-2 text-xs text-black/45">联系方式：{report.contact}</p>}
                  <div className="mt-4 grid gap-3">
                    <label className="text-xs font-medium text-black/55">公开处理摘要<textarea value={reportDrafts[report.id]?.public_summary || ""} onChange={(event) => setReportDrafts((current) => ({ ...current, [report.id]: { ...(current[report.id] || { merchant_response: "" }), public_summary: event.target.value } }))} maxLength={500} rows={2} placeholder="只写适合公开的事实结论，不要复制联系方式或私密内容。" className="mt-1.5 w-full rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm text-[color:var(--ink)]" /></label>
                    <label className="text-xs font-medium text-black/55">商家公开回应 <span className="font-normal">选填</span><textarea value={reportDrafts[report.id]?.merchant_response || ""} onChange={(event) => setReportDrafts((current) => ({ ...current, [report.id]: { ...(current[report.id] || { public_summary: "" }), merchant_response: event.target.value } }))} maxLength={1000} rows={2} className="mt-1.5 w-full rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm text-[color:var(--ink)]" /></label>
                  </div>
                </div>
                <div className="flex gap-2 md:self-end">
                  <button onClick={() => resolveReport(report.id, "resolved")} className="tactile flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-3 py-2 text-sm text-white"><Check size={16} />已处理</button>
                  <button onClick={() => resolveReport(report.id, "rejected")} className="tactile flex items-center gap-2 rounded-[10px] border hairline px-3 py-2 text-sm"><X size={16} />驳回</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {offers.length > 0 && (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 font-semibold">最近报价</div>
          <div className="divide-y divide-[color:var(--line)]">
            {offers.map((offer) => (
              <div key={offer.id} className="grid gap-3 px-5 py-4 xl:grid-cols-[1fr_210px_100px_190px] xl:items-center">
                <div>
                  <p className="font-medium">{offer.shop}</p>
                  <p className="mt-1 text-sm text-black/55">{offer.title}</p>
                </div>
                <select
                  value={offer.product_slug || ""}
                  onChange={(event) => patchOffer(offer.id, { product_slug: event.target.value, approved: true })}
                  className="rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm"
                >
                  <option value="" disabled>未分类</option>
                  {PRODUCT_OPTIONS.map((slug) => <option key={slug} value={slug}>{slug}</option>)}
                </select>
                <div className="text-sm">
                  {money(offer.price, offer.currency)}<br />
                  <span className="text-black/40">{offer.stock_status}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={`status-pill ${offer.approved ? "status-success" : "status-info"}`}>{offer.approved ? "已公开" : "待审核"}</span>
                  <button
                    onClick={() => patchOffer(offer.id, { approved: !offer.approved })}
                    className={`tactile rounded-[10px] px-3 py-2 text-sm ${offer.approved ? "bg-[color:var(--accent)]" : "border hairline"}`}
                  >
                    {offer.approved ? "撤回公开" : "批准公开"}
                  </button>
                  <button
                    onClick={() => patchOffer(offer.id, { active: !offer.active, hidden_reason: offer.active ? "管理员隐藏" : "" })}
                    className="tactile flex items-center justify-center gap-2 rounded-[10px] border hairline px-3 py-2 text-sm"
                  >
                    {offer.active ? <EyeSlash size={16} /> : <Eye size={16} />}{offer.active ? "隐藏" : "恢复"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
