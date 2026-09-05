"use client";

import { useEffect, useState } from "react";
import { ArrowClockwise, Check, Eye, EyeSlash, Key, MagnifyingGlass, X } from "@phosphor-icons/react";
import { money } from "@/lib/format";
import { SourceDiscoveryPanel } from "@/components/source-discovery-panel";
import { BRAND_TABS, type BrandName, PRODUCT_TABS, ALL_PRODUCTS } from "@/lib/catalog";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
type CategoryMode = "all" | "restricted" | "unclassified" | BrandName;
type StatusFilter = "all" | "active" | "pending";

type Stats = {
  shops: number;
  products: number;
  offers: number;
  public_offers: number;
  restricted_offers?: number;
  unclassified_offers?: number;
  open_corrections: number;
  pending_source_intakes: number;
  open_reports: number;
  last_scan_at: string | null;
};

type AdminOffer = {
  id: number;
  shop: string;
  shop_token?: string;
  title: string;
  original_category?: string | null;
  product_slug: string | null;
  product_name?: string | null;
  brand?: string | null;
  price: string | null;
  currency: string;
  stock_status: string;
  approved: boolean;
  active: boolean;
  hidden_reason?: string | null;
  observed_at?: string | null;
  updated_at?: string | null;
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

type SourceType = "unknown" | "ldxp" | "dujiao_next" | "merchant_json" | "woocommerce" | "16688" | "schema_org" | "other";

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

export function AdminPanel({ previewState }: { previewState?: "error" }) {
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [offers, setOffers] = useState<AdminOffer[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<CategoryMode>("all");
  const [selectedProductSlug, setSelectedProductSlug] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [offerSearch, setOfferSearch] = useState("");
  const [reclassifyingOfferId, setReclassifyingOfferId] = useState<number | null>(null);
  const [actionToast, setActionToast] = useState<string>("");
  const [reports, setReports] = useState<Report[]>([]);
  const [intakes, setIntakes] = useState<SourceIntake[]>([]);
  const [targetIntakeId, setTargetIntakeId] = useState<number | null>(null);
  const [reportDrafts, setReportDrafts] = useState<Record<number, { public_summary: string; merchant_response: string }>>({});
  const [intakeReasons, setIntakeReasons] = useState<Record<number, string>>({});
  const [error, setError] = useState(previewState === "error" ? "管理数据暂时无法加载。输入密钥后可以重新连接。" : "");
  const headers = { "X-Admin-Key": key };

  useEffect(() => {
    const intakeId = Number(new URLSearchParams(window.location.search).get("intake"));
    if (Number.isInteger(intakeId) && intakeId > 0) setTargetIntakeId(intakeId);
  }, []);

  useEffect(() => {
    if (targetIntakeId === null || !intakes.some((intake) => intake.id === targetIntakeId)) return;
    document.getElementById(`source-intake-${targetIntakeId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [intakes, targetIntakeId]);

  async function loadOffers(
    category: CategoryMode = selectedCategory,
    productSlug: string = selectedProductSlug,
    status: StatusFilter = statusFilter,
    search: string = offerSearch
  ) {
    const params = new URLSearchParams();
    params.set("limit", "100");
    if (category === "restricted") {
      params.set("status", "restricted");
    } else if (category === "unclassified") {
      params.set("status", "unclassified");
    } else {
      if (category !== "all") params.set("brand", category);
      if (status !== "all") params.set("status", status);
    }
    if (productSlug.trim() && category !== "restricted" && category !== "unclassified") {
      params.set("product_slug", productSlug.trim());
    }
    if (search.trim()) params.set("q", search.trim());
    const response = await fetch(`${API}/api/v1/admin/offers?${params.toString()}`, { headers });
    if (response.ok) {
      setOffers(await response.json());
    }
  }

  async function load() {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "100");
      if (selectedCategory === "restricted") {
        params.set("status", "restricted");
      } else if (selectedCategory === "unclassified") {
        params.set("status", "unclassified");
      } else {
        if (selectedCategory !== "all") params.set("brand", selectedCategory);
        if (statusFilter !== "all") params.set("status", statusFilter);
      }
      if (selectedProductSlug.trim() && selectedCategory !== "restricted" && selectedCategory !== "unclassified") {
        params.set("product_slug", selectedProductSlug.trim());
      }
      if (offerSearch.trim()) params.set("q", offerSearch.trim());

      const [statsResponse, offersResponse, reportsResponse, intakesResponse] = await Promise.all([
        fetch(`${API}/api/v1/admin/stats`, { headers }),
        fetch(`${API}/api/v1/admin/offers?${params.toString()}`, { headers }),
        fetch(`${API}/api/v1/admin/reports?status=open`, { headers }),
        fetch(`${API}/api/v1/admin/source-intakes`, { headers }),
      ]);
      if (!statsResponse.ok || !offersResponse.ok || !reportsResponse.ok || !intakesResponse.ok) {
        setError("管理密钥无效，或 API 无法访问。密钥仍保留在当前页面，可以修改后重试。");
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
    } catch {
      setError("管理 API 暂时无法访问。密钥仍保留在当前页面，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function patchOffer(offerId: number, body: Record<string, unknown>) {
    const response = await fetch(`${API}/api/v1/admin/offers/${offerId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
    if (response.ok) {
      await loadOffers();
      const statsRes = await fetch(`${API}/api/v1/admin/stats`, { headers });
      if (statsRes.ok) setStats(await statsRes.json());
    }
  }

  async function reclassifySingleOffer(offerId: number) {
    setReclassifyingOfferId(offerId);
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/offers/${offerId}/reclassify`, {
        method: "POST",
        headers,
      });
      if (response.ok) {
        const data = await response.json();
        const msg = data.product_slug
          ? `已成功归类为 ${data.product_slug}（置信度 ${data.confidence}%）`
          : "分类器判定该商品未命中任何标准产品（保持未归类）";
        setActionToast(`报价 #${offerId} 自动分类完成：${msg}`);
        await loadOffers();
        const statsRes = await fetch(`${API}/api/v1/admin/stats`, { headers });
        if (statsRes.ok) setStats(await statsRes.json());
      } else {
        setError(`报价 #${offerId} 自动分类失败`);
      }
    } catch {
      setError(`报价 #${offerId} 自动分类请求失败`);
    } finally {
      setReclassifyingOfferId(null);
    }
  }

  async function reclassify() {
    const response = await fetch(`${API}/api/v1/admin/reclassify`, {
      method: "POST",
      headers,
    });
    if (response.ok) {
      const data = await response.json();
      setActionToast(`全量重新分类完成：变更 ${data.changed} 条，未分类 ${data.unclassified} 条`);
      await load();
    }
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

  async function updateIntake(intakeId: number, action: "approve" | "reject" | "retry" | "redetect") {
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
    if (response.ok) {
      await load();
    } else {
      const data = await response.json().catch(() => null);
      setError(data?.detail || "收录申请状态更新失败，请刷新后重试。");
    }
  }

  async function updateIntakePlatform(intakeId: number, platform: string) {
    const response = await fetch(`${API}/api/v1/admin/source-intakes/${intakeId}/platform`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ platform }),
    });
    if (response.ok) {
      await load();
    } else {
      const data = await response.json().catch(() => null);
      setError(data?.detail || "平台类型修改失败，请刷新后重试。");
    }
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
    "16688": "16688",
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
    <div className="space-y-8" data-vds-layer="evidence" data-vds-action="credential-gate live-stats review-queue explicit-decisions">
      <section className="surface-panel grid gap-4 p-5 md:grid-cols-[1fr_auto_auto] md:items-end" aria-labelledby="admin-access-title">
        <label className="text-sm font-medium">
          <span id="admin-access-title">管理密钥</span>
          <span className="mt-2 flex min-h-11 items-center gap-2 rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 focus-within:border-[color:var(--focus)]">
            <Key size={18} />
            <input
              value={key}
              onChange={(event) => setKey(event.target.value)}
              type={showKey ? "text" : "password"}
              className="w-full bg-transparent py-3 outline-none"
            />
            <button type="button" onClick={() => setShowKey((value) => !value)} aria-label={showKey ? "隐藏管理密钥" : "显示管理密钥"} className="grid size-11 shrink-0 place-items-center rounded-[7px] text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)]">{showKey ? <EyeSlash size={18} /> : <Eye size={18} />}</button>
          </span>
        </label>
        <button type="button" onClick={load} disabled={!key.trim() || loading} className="button-primary tactile disabled:cursor-not-allowed disabled:opacity-50">
          {loading ? "正在连接" : "验证并加载"}
        </button>
        <button type="button" onClick={reclassify} disabled={!stats || loading} className="button-secondary tactile disabled:cursor-not-allowed disabled:opacity-50">
          <ArrowClockwise size={17} />重新分类
        </button>
      </section>

      {error && <p role="alert" className="rounded-[9px] border border-[color:var(--danger)]/25 bg-[color:var(--danger-soft)] p-4 text-[color:var(--danger)]">{error}</p>}
      {!stats && !error && <section className="surface-subtle p-5" role="status"><p className="section-kicker">尚未连接</p><p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">输入管理密钥后加载当前统计、收录申请、纠错队列和最近报价。</p></section>}

      {stats && (
        <section className="data-strip sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {[
            ["店铺", stats.shops],
            ["标准产品", stats.products],
            ["全部报价", stats.offers],
            ["公开报价", stats.public_offers],
            ["受限报价", stats.restricted_offers ?? 0],
            ["未分类商品", stats.unclassified_offers ?? 0],
            ["待处理纠错", stats.open_corrections],
            ["待初审收录", stats.pending_source_intakes],
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
                    <p className="mono text-xs text-black/40">#{intake.id}</p>
                    <span className="status-pill status-info">{intakeStatusLabels[intake.status] || intake.status}</span>
                    <div className="flex items-center gap-1.5 ml-1">
                      <span className="text-xs text-black/50">平台:</span>
                      <select
                        value={intake.source_type}
                        onChange={(e) => updateIntakePlatform(intake.id, e.target.value)}
                        className="rounded-[6px] border hairline bg-[color:var(--panel)] px-2 py-0.5 text-xs text-[color:var(--ink)]"
                      >
                        <option value="ldxp">链动小铺 (ldxp)</option>
                        <option value="dujiao_next" disabled>独角数卡 (dujiao_next - 已暂停)</option>
                        <option value="16688">16688发卡 (16688)</option>
                        <option value="woocommerce">WooCommerce</option>
                        <option value="merchant_json">商家 JSON Feed</option>
                        <option value="schema_org">Schema.org</option>
                        <option value="other">其他独立站</option>
                        <option value="unknown">未知来源</option>
                      </select>
                    </div>
                  </div>
                  <p className="mt-2 break-all text-sm font-medium">{intake.shop_name || "未填写来源名称"}</p>
                  <p className="mt-1 break-all text-xs leading-5 text-black/55">{intake.source_url}</p>
                  <p className="mt-2 text-xs text-black/50">联系邮箱：{intake.contact_email} · 商品数：{intake.product_count} · 重试次数：{intake.attempt_count}</p>
                  {intake.note && <p className="mt-2 whitespace-pre-line text-sm leading-6 text-black/65">申请说明：{intake.note}</p>}
                  {intake.source_type === "other" && intake.status === "pending_review" && <p className="mt-2 text-sm leading-6 text-black/65">提示：如该店铺为链动小铺、独角数卡等支持的平台，可在上方切换类型或点击“重新检测”；点击批准将自动按检测平台接入。</p>}
                  {["merchant_json", "woocommerce", "16688", "schema_org"].includes(intake.source_type) && intake.status === "approved" && <p className="mt-2 text-sm leading-6 text-black/65">等待目录发布流程安全拉取并分类商品；成功进入完整快照后才会公开。</p>}
                  {intake.failure_reason && <p className="mt-2 rounded-[10px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm leading-6 text-[color:var(--danger)]">失败原因：{intake.failure_reason}</p>}
                  {Object.keys(intake.email_status).length > 0 && <p className="mt-3 text-xs text-black/50">邮件状态：{Object.entries(intake.email_status).map(([event, mailStatus]) => `${event} ${emailStatusLabel(mailStatus)}`).join(" · ")}</p>}
                  {intake.status === "pending_review" && <label className="mt-4 block text-xs font-medium text-black/55">驳回原因<input value={intakeReasons[intake.id] || ""} onChange={(event) => setIntakeReasons((current) => ({ ...current, [intake.id]: event.target.value }))} maxLength={500} placeholder="仅在驳回时必填" className="field mt-1.5 text-sm" /></label>}
                </div>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  {intake.status === "pending_review" && (
                    <>
                      <button onClick={() => updateIntake(intake.id, "approve")} className="button-primary tactile">
                        <Check size={16} />
                        {intake.source_type === "ldxp" ? "批准并验证" : intake.source_type === "other" ? "批准接入" : "批准并加入发布队列"}
                      </button>
                      <button onClick={() => updateIntake(intake.id, "redetect")} className="tactile rounded-[10px] border hairline px-3 py-2 text-sm" title="根据最新探测规则重新识别平台">
                        <ArrowClockwise size={16} className="mr-1 inline" />
                        重新检测
                      </button>
                      <button onClick={() => updateIntake(intake.id, "reject")} className="button-danger tactile">
                        <X size={16} />
                        驳回
                      </button>
                    </>
                  )}
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

      {stats && (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4">
            <h2 className="text-base font-semibold">报价与分类管理</h2>
            <p className="mt-0.5 text-xs text-black/55">
              前后台分类与展示顺序严格对齐。支持按品牌、产品分类及【受限/已隐藏】专区分类查看，并在每个商品项直接执行公开审批、限制隐藏、自动算法检测及目标归类。
            </p>
          </div>

          {/* Navigation Rails matching Frontend */}
          <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 space-y-3">
            {/* Level 1: Brand & Special Categories */}
            <nav className="filter-rail flex-wrap gap-1.5" aria-label="管理分类品牌与视图">
              <span className="filter-label">品牌/专区</span>
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory("all");
                  setSelectedProductSlug("");
                  loadOffers("all", "", statusFilter, offerSearch);
                }}
                aria-current={selectedCategory === "all" ? "page" : undefined}
                className="filter-chip"
              >
                全部品牌
              </button>
              {BRAND_TABS.map((brand) => (
                <button
                  key={brand}
                  type="button"
                  onClick={() => {
                    setSelectedCategory(brand);
                    setSelectedProductSlug("");
                    loadOffers(brand, "", statusFilter, offerSearch);
                  }}
                  aria-current={selectedCategory === brand ? "page" : undefined}
                  className="filter-chip"
                >
                  {brand}
                </button>
              ))}
              <div className="mx-1 h-5 w-px bg-[color:var(--line-strong)] self-center hidden sm:block" />
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory("restricted");
                  setSelectedProductSlug("");
                  loadOffers("restricted", "", "all", offerSearch);
                }}
                aria-current={selectedCategory === "restricted" ? "page" : undefined}
                className={`filter-chip flex items-center gap-1.5 ${
                  selectedCategory === "restricted"
                    ? "!bg-[color:var(--danger)] !text-white !border-[color:var(--danger)]"
                    : "border-[color:var(--danger)]/40 text-[color:var(--danger)] hover:bg-[color:var(--danger-soft)]"
                }`}
              >
                <span>🚫 受限/已隐藏</span>
                {(stats.restricted_offers ?? 0) > 0 && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 mono text-[10px] ${
                      selectedCategory === "restricted"
                        ? "bg-white/20 text-white"
                        : "bg-[color:var(--danger-soft)] text-[color:var(--danger)]"
                    }`}
                  >
                    {stats.restricted_offers}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory("unclassified");
                  setSelectedProductSlug("");
                  loadOffers("unclassified", "", "all", offerSearch);
                }}
                aria-current={selectedCategory === "unclassified" ? "page" : undefined}
                className={`filter-chip flex items-center gap-1.5 ${
                  selectedCategory === "unclassified"
                    ? ""
                    : "text-black/70 hover:bg-[color:var(--subtle)]"
                }`}
              >
                <span>❓ 未分类商品</span>
                {(stats.unclassified_offers ?? 0) > 0 && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 mono text-[10px] ${
                      selectedCategory === "unclassified"
                        ? "bg-white/20 text-white"
                        : "bg-black/5 text-black/60"
                    }`}
                  >
                    {stats.unclassified_offers}
                  </span>
                )}
              </button>
            </nav>

            {/* Level 2: Product Types Rail (when Brand is active) */}
            {selectedCategory !== "restricted" && selectedCategory !== "unclassified" && (
              <nav className="filter-rail border-t border-[color:var(--line)] pt-3 flex-wrap gap-1.5" aria-label="商品类型筛选">
                <span className="filter-label">商品分类</span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProductSlug("");
                    loadOffers(selectedCategory, "", statusFilter, offerSearch);
                  }}
                  aria-current={selectedProductSlug === "" ? "page" : undefined}
                  className="filter-chip"
                >
                  {selectedCategory === "all" ? "全部商品" : `全部 ${selectedCategory}`}
                </button>
                {(selectedCategory === "all" ? ALL_PRODUCTS : PRODUCT_TABS[selectedCategory as BrandName] || []).map((tab) => (
                  <button
                    key={tab.slug}
                    type="button"
                    onClick={() => {
                      setSelectedProductSlug(tab.slug);
                      loadOffers(selectedCategory, tab.slug, statusFilter, offerSearch);
                    }}
                    aria-current={selectedProductSlug === tab.slug ? "page" : undefined}
                    className="filter-chip"
                  >
                    {selectedCategory === "all" && "brand" in tab && (
                      <span className="text-[10px] opacity-60 mr-1">{String(tab.brand)}</span>
                    )}
                    {tab.label}
                  </button>
                ))}
              </nav>
            )}

            {/* Specialized Information Banner for Restricted / Unclassified */}
            {selectedCategory === "restricted" && (
              <div className="rounded-[9px] border border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] px-4 py-3 text-xs leading-5 text-[color:var(--danger)]">
                <strong>🚫 当前分类：受限/已隐藏专区（共 {stats.restricted_offers ?? 0} 条）</strong>
                <p className="mt-1">
                  展示所有被分类拦截机制判定为教程/非标品、缺乏账号核心凭证，或由管理员手动限制隐藏的商品报价。可在此核查商家原始分类与拦截原因，并支持一键【恢复公开】或手动指定重新归类。
                </p>
              </div>
            )}
            {selectedCategory === "unclassified" && (
              <div className="rounded-[9px] border border-[color:var(--warning)]/30 bg-[color:var(--warning-soft)] px-4 py-3 text-xs leading-5 text-[color:var(--ink)]">
                <strong>❓ 当前分类：未分类商品专区（共 {stats.unclassified_offers ?? 0} 条）</strong>
                <p className="mt-1">
                  展示已从各店铺采集入库但暂未归类到任何标准产品的商品。可在此手动选择目标分类或点击【自动分类】调用算法规则重新识别。
                </p>
              </div>
            )}
          </div>

          {/* Search & Status Sub-Filter */}
          <div className="grid gap-3 border-b border-[color:var(--line)] bg-[color:var(--panel)] p-4 sm:grid-cols-[1fr_auto]">
            <div className="relative">
              <input
                value={offerSearch}
                onChange={(e) => setOfferSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch);
                  }
                }}
                placeholder="按标题、店铺名称或受限拦截原因搜索..."
                className="w-full rounded-[9px] border border-[color:var(--line-strong)] bg-transparent py-2 pl-9 pr-3 text-sm outline-none focus:border-[color:var(--focus)]"
              />
              <MagnifyingGlass size={16} className="absolute left-3 top-3 text-black/40" />
            </div>
            <div className="flex items-center gap-2">
              {selectedCategory !== "restricted" && selectedCategory !== "unclassified" && (
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    const nextStatus = e.target.value as StatusFilter;
                    setStatusFilter(nextStatus);
                    loadOffers(selectedCategory, selectedProductSlug, nextStatus, offerSearch);
                  }}
                  className="rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-sm text-black/75 outline-none"
                >
                  <option value="all">全部公开状态</option>
                  <option value="active">仅看公开中</option>
                  <option value="pending">仅看未公开/待审</option>
                </select>
              )}
              <button
                type="button"
                onClick={() => loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch)}
                className="button-secondary tactile"
              >
                搜索筛选
              </button>
            </div>
          </div>

          {actionToast && (
            <div className="flex items-center justify-between border-b border-[color:var(--line)] bg-[color:var(--brand-soft)] px-5 py-2.5 text-xs text-[color:var(--ink)]">
              <span>{actionToast}</span>
              <button type="button" onClick={() => setActionToast("")} className="text-black/40 hover:text-black">
                <X size={14} />
              </button>
            </div>
          )}

          {offers.length === 0 ? (
            <div className="p-8 text-center text-sm text-black/45">
              当前分类（{selectedCategory === "restricted" ? "受限/已隐藏" : selectedCategory === "unclassified" ? "未分类" : selectedCategory}）及筛选条件下暂无商品报价。
            </div>
          ) : (
            <div className="divide-y divide-[color:var(--line)]">
              {offers.map((offer) => (
                <div key={offer.id} className="grid gap-3 px-5 py-4 xl:grid-cols-[1fr_240px_100px_auto] xl:items-center">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-xs text-black/40">#{offer.id} · {offer.shop}</span>
                      {!offer.active && <span className="status-pill status-danger">已隐藏/受限</span>}
                      {!offer.approved && <span className="status-pill status-info">未公开</span>}
                      {!offer.product_slug && <span className="status-pill status-warning">未归类</span>}
                      {offer.approved && offer.active && offer.product_slug && (
                        <span className="status-pill status-success">公开中</span>
                      )}
                      {offer.product_slug && (
                        <span className="rounded-[6px] bg-[color:var(--brand-soft)] px-2 py-0.5 text-xs font-medium text-[color:var(--brand)]">
                          {offer.brand ? `${offer.brand} / ` : ""}{offer.product_name || offer.product_slug}
                        </span>
                      )}
                    </div>
                    <p className="mt-1.5 font-medium text-sm text-[color:var(--ink)]">{offer.title}</p>
                    {offer.original_category && (
                      <p className="mt-1 text-xs text-black/50">商家原始分类：{offer.original_category}</p>
                    )}
                    {offer.hidden_reason && (
                      <div className="mt-2 rounded-[8px] border border-[color:var(--danger)]/25 bg-[color:var(--danger-soft)] px-2.5 py-1.5 text-xs text-[color:var(--danger)]">
                        <strong>🚫 受限拦截原因：</strong>{offer.hidden_reason}
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="mb-1 block text-[11px] font-medium text-black/50">重新分类目标：</label>
                    <select
                      value={offer.product_slug || ""}
                      onChange={(event) =>
                        patchOffer(offer.id, {
                          product_slug: event.target.value,
                          approved: Boolean(event.target.value),
                        })
                      }
                      className="w-full rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-xs"
                    >
                      <option value="">未分类 / 暂不归类</option>
                      {BRAND_TABS.map((brand) => (
                        <optgroup key={brand} label={brand}>
                          {PRODUCT_TABS[brand].map((p) => (
                            <option key={p.slug} value={p.slug}>
                              {p.label} ({p.slug})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>

                  <div className="text-sm">
                    {money(offer.price, offer.currency)}
                    <br />
                    <span className="text-xs text-black/40">{offer.stock_status}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={reclassifyingOfferId === offer.id}
                      onClick={() => reclassifySingleOffer(offer.id)}
                      className="tactile flex items-center gap-1.5 rounded-[10px] border hairline px-3 py-2 text-xs text-black/75 hover:bg-[color:var(--subtle)] disabled:opacity-50"
                      title="使用最新分类器规则对该单品重新检测"
                    >
                      <ArrowClockwise size={14} className={reclassifyingOfferId === offer.id ? "animate-spin" : ""} />
                      自动分类
                    </button>
                    {!offer.active || Boolean(offer.hidden_reason) ? (
                      <button
                        type="button"
                        onClick={() =>
                          patchOffer(offer.id, {
                            active: true,
                            approved: true,
                            hidden_reason: "",
                          })
                        }
                        className="tactile flex items-center gap-1.5 rounded-[10px] border border-[color:var(--brand)] bg-[color:var(--brand-soft)] px-3 py-2 text-xs font-medium text-[color:var(--brand)] hover:opacity-90"
                      >
                        <Eye size={14} />
                        恢复公开
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() =>
                          patchOffer(offer.id, {
                            active: false,
                            hidden_reason: "管理员限制",
                          })
                        }
                        className="tactile flex items-center gap-1.5 rounded-[10px] border hairline px-3 py-2 text-xs text-black/60 hover:text-[color:var(--danger)]"
                      >
                        <EyeSlash size={14} />
                        隐藏/限制
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => patchOffer(offer.id, { approved: !offer.approved })}
                      className={`tactile rounded-[10px] px-3 py-2 text-xs ${
                        offer.approved ? "bg-[color:var(--accent)] text-black/70" : "border hairline text-black/80 font-medium"
                      }`}
                    >
                      {offer.approved ? "撤回公开" : "批准公开"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
