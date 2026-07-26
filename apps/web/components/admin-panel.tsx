"use client";

import { useState } from "react";
import { ArrowClockwise, Check, Eye, EyeSlash, Key, X } from "@phosphor-icons/react";

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
  open_reports: number;
  last_scan_at: string | null;
};

type AdminOffer = {
  id: number;
  shop: string;
  title: string;
  product_slug: string | null;
  price: string | null;
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
  created_at: string;
};

export function AdminPanel() {
  const [key, setKey] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [offers, setOffers] = useState<AdminOffer[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState("");
  const headers = { "X-Admin-Key": key };

  async function load() {
    setError("");
    const [statsResponse, offersResponse, reportsResponse] = await Promise.all([
      fetch(`${API}/api/v1/admin/stats`, { headers }),
      fetch(`${API}/api/v1/admin/offers?limit=50`, { headers }),
      fetch(`${API}/api/v1/admin/reports?status=open`, { headers }),
    ]);
    if (!statsResponse.ok || !offersResponse.ok || !reportsResponse.ok) {
      setError("管理密钥无效，或 API 无法访问。");
      return;
    }
    setStats(await statsResponse.json());
    setOffers(await offersResponse.json());
    setReports(await reportsResponse.json());
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
    const response = await fetch(`${API}/api/v1/admin/reports/${reportId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ status }),
    });
    if (response.ok) await load();
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-4 rounded-[18px] border hairline bg-[color:var(--panel)] p-5 md:grid-cols-[1fr_auto_auto] md:items-end">
        <label className="text-sm font-medium">
          管理密钥
          <span className="mt-2 flex items-center gap-2 rounded-[10px] border hairline bg-white px-3">
            <Key size={18} />
            <input
              value={key}
              onChange={(event) => setKey(event.target.value)}
              type="password"
              className="w-full bg-transparent py-3 outline-none"
            />
          </span>
        </label>
        <button onClick={load} className="tactile rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm text-white">
          加载后台
        </button>
        <button onClick={reclassify} className="tactile flex items-center justify-center gap-2 rounded-[10px] border border-black px-5 py-3 text-sm">
          <ArrowClockwise size={17} />重新分类
        </button>
      </section>

      {error && <p className="rounded-[10px] bg-[#f2d8d2] p-4 text-[color:var(--danger)]">{error}</p>}

      {stats && (
        <section className="grid gap-px overflow-hidden rounded-[18px] border hairline bg-[color:var(--line)] sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["店铺", stats.shops],
            ["标准产品", stats.products],
            ["全部报价", stats.offers],
            ["公开报价", stats.public_offers],
            ["待处理举报", stats.open_reports],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-[color:var(--panel)] p-5">
              <p className="mono text-xs text-black/40">{label}</p>
              <p className="mt-3 text-3xl font-semibold">{value}</p>
            </div>
          ))}
        </section>
      )}

      {reports.length > 0 && (
        <section className="overflow-hidden rounded-[18px] border hairline bg-[color:var(--panel)]">
          <div className="border-b hairline px-5 py-4 font-semibold">待处理举报</div>
          <div className="divide-y divide-[color:var(--line)]">
            {reports.map((report) => (
              <div key={report.id} className="grid gap-4 px-5 py-4 md:grid-cols-[1fr_auto] md:items-center">
                <div>
                  <p className="mono text-xs uppercase text-black/40">{report.kind} · 报价 #{report.offer_id || "暂无"}</p>
                  <p className="mt-2 text-sm leading-6">{report.message}</p>
                  {report.contact && <p className="mt-2 text-xs text-black/45">联系方式：{report.contact}</p>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => resolveReport(report.id, "resolved")} className="tactile flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-3 py-2 text-sm text-white"><Check size={16} />已处理</button>
                  <button onClick={() => resolveReport(report.id, "rejected")} className="tactile flex items-center gap-2 rounded-[10px] border hairline px-3 py-2 text-sm"><X size={16} />驳回</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {offers.length > 0 && (
        <section className="overflow-hidden rounded-[18px] border hairline bg-[color:var(--panel)]">
          <div className="border-b hairline px-5 py-4 font-semibold">最近报价</div>
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
                  className="rounded-[10px] border hairline bg-white px-3 py-2 text-sm"
                >
                  <option value="" disabled>未分类</option>
                  {PRODUCT_OPTIONS.map((slug) => <option key={slug} value={slug}>{slug}</option>)}
                </select>
                <div className="text-sm">
                  ¥{offer.price || "暂无"}<br />
                  <span className="text-black/40">{offer.stock_status}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => patchOffer(offer.id, { approved: !offer.approved })}
                    className={`tactile rounded-[10px] px-3 py-2 text-sm ${offer.approved ? "bg-[color:var(--accent)]" : "border hairline"}`}
                  >
                    {offer.approved ? "已发布" : "待审核"}
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
