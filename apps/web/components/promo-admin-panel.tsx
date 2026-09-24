"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowClockwise,
  ArrowSquareOut,
  ArrowsLeftRight,
  Eye,
  EyeSlash,
  Megaphone,
  PencilSimple,
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import {
  AD_PLACEMENTS,
  type AdPlacement,
  type AdSlotAdmin,
  type AdSlotInput,
  type RelayStationAdmin,
  type RelayStationInput,
} from "@/lib/types";

export const AD_PLACEMENT_LABELS: Record<AdPlacement, { label: string; hint: string }> = {
  home_hero: { label: "首页 · 概览下方", hint: "首页搜索区与统计栏之间，全站曝光最高。" },
  catalog_top: { label: "报价目录 · 顶部", hint: "/products 品牌目录列表上方（不含单个商品页）。" },
  product_offers: { label: "商品页 · 报价列表上方", hint: "每个标准商品工作区的报价表格上方，紧凑样式。" },
  relay_hub: { label: "中转站专区 · 顶部", hint: "/relays 中转站目录页顶部。" },
  sidebar: { label: "预留 · 侧栏", hint: "暂未接入页面，供后续版式使用。" },
};

const EMPTY_AD: AdSlotInput = {
  placement: "catalog_top",
  title: "",
  description: "",
  sponsor_name: "",
  badge: "广告",
  cta_text: "了解详情",
  link_url: "",
  image_url: "",
  sort_order: 100,
  is_enabled: true,
  starts_at: null,
  ends_at: null,
};

const EMPTY_RELAY: RelayStationInput = {
  name: "",
  url: "",
  tagline: "",
  description: "",
  supported_models: [],
  price_note: "",
  billing_note: "",
  tags: [],
  is_sponsored: false,
  is_enabled: true,
  sort_order: 100,
};

type RelayDraft = Omit<RelayStationInput, "supported_models" | "tags"> & { supported_models_text: string; tags_text: string };

function splitList(value: string): string[] {
  return Array.from(new Set(value.split(/[\n,，;；]+/).map((item) => item.trim()).filter(Boolean)));
}

function toDatetimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function adStatus(slot: AdSlotAdmin): { label: string; tone: "success" | "info" | "warning" | "muted" } {
  if (!slot.is_enabled) return { label: "已停用", tone: "muted" };
  const now = Date.now();
  if (slot.starts_at && new Date(slot.starts_at).getTime() > now) return { label: "待上线", tone: "info" };
  if (slot.ends_at && new Date(slot.ends_at).getTime() < now) return { label: "已过期", tone: "warning" };
  return { label: "投放中", tone: "success" };
}

function errorDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : ""))
        .filter(Boolean)
        .join("；") || fallback;
    }
  }
  return fallback;
}

export function PromoAdminPanel({
  apiBase,
  headers,
  adSlotsEnabled,
  relayHubEnabled,
  onToggleSetting,
  togglingSetting,
}: {
  apiBase: string;
  headers: Record<string, string>;
  adSlotsEnabled: boolean;
  relayHubEnabled: boolean;
  onToggleSetting: (key: "ad_slots_enabled" | "relay_hub_enabled", value: boolean) => Promise<void> | void;
  togglingSetting: boolean;
}) {
  const [subTab, setSubTab] = useState<"ads" | "relays">("ads");
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  }, []);

  // The parent recreates the header object on every render; key the memo on
  // its serialised value so the load callbacks (and the mount effect that
  // depends on them) stay stable.
  const headerKey = JSON.stringify(headers);
  const stableHeaders = useMemo<Record<string, string>>(() => JSON.parse(headerKey), [headerKey]);
  const jsonHeaders = useMemo(() => ({ "Content-Type": "application/json", ...stableHeaders }), [stableHeaders]);

  // ----------------------------------------------------------------- ads --
  const [ads, setAds] = useState<AdSlotAdmin[]>([]);
  const [loadingAds, setLoadingAds] = useState(false);
  const [adDraft, setAdDraft] = useState<AdSlotInput>(EMPTY_AD);
  const [editingAdId, setEditingAdId] = useState<number | null>(null);
  const [adFormOpen, setAdFormOpen] = useState(false);
  const [savingAd, setSavingAd] = useState(false);
  const [adError, setAdError] = useState("");

  const loadAds = useCallback(async () => {
    setLoadingAds(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/ads`, { credentials: "include", headers: stableHeaders });
      if (!res.ok) throw new Error(`读取广告栏位失败 (${res.status})`);
      setAds((await res.json()) as AdSlotAdmin[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "读取广告栏位失败");
    } finally {
      setLoadingAds(false);
    }
  }, [apiBase, stableHeaders]);

  const openAdForm = (slot?: AdSlotAdmin) => {
    setAdError("");
    if (slot) {
      setEditingAdId(slot.id);
      setAdDraft({
        placement: (AD_PLACEMENTS as readonly string[]).includes(slot.placement) ? (slot.placement as AdPlacement) : "catalog_top",
        title: slot.title,
        description: slot.description,
        sponsor_name: slot.sponsor_name,
        badge: slot.badge,
        cta_text: slot.cta_text,
        link_url: slot.link_url,
        image_url: slot.image_url,
        sort_order: slot.sort_order,
        is_enabled: slot.is_enabled,
        starts_at: slot.starts_at,
        ends_at: slot.ends_at,
      });
    } else {
      setEditingAdId(null);
      setAdDraft(EMPTY_AD);
    }
    setAdFormOpen(true);
  };

  const submitAd = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!adDraft.title.trim()) {
      setAdError("请填写广告标题。");
      return;
    }
    if (adDraft.link_url && !/^(\/(?!\/)|https:\/\/)/i.test(adDraft.link_url.trim())) {
      setAdError("跳转链接必须是站内路径（以 / 开头）或公开 HTTPS 地址。");
      return;
    }
    setSavingAd(true);
    setAdError("");
    try {
      const isEdit = editingAdId !== null;
      const body = isEdit
        ? { ...adDraft, clear_schedule: !adDraft.starts_at && !adDraft.ends_at }
        : adDraft;
      const res = await fetch(`${apiBase}/api/v1/admin/ads${isEdit ? `/${editingAdId}` : ""}`, {
        method: isEdit ? "PATCH" : "POST",
        credentials: "include",
        headers: jsonHeaders,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(errorDetail(payload, `保存失败 (${res.status})`));
      }
      showToast(isEdit ? "广告栏位已更新" : "广告栏位已创建");
      setAdFormOpen(false);
      await loadAds();
    } catch (e) {
      setAdError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingAd(false);
    }
  };

  const toggleAd = async (slot: AdSlotAdmin) => {
    const res = await fetch(`${apiBase}/api/v1/admin/ads/${slot.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: jsonHeaders,
      body: JSON.stringify({ is_enabled: !slot.is_enabled }),
    });
    if (res.ok) {
      showToast(slot.is_enabled ? "已停用该广告" : "已启用该广告");
      await loadAds();
    } else {
      setError(`更新失败 (${res.status})`);
    }
  };

  const deleteAd = async (slot: AdSlotAdmin) => {
    if (!window.confirm(`确定删除广告「${slot.title}」？点击统计将一并删除。`)) return;
    const res = await fetch(`${apiBase}/api/v1/admin/ads/${slot.id}`, { method: "DELETE", credentials: "include", headers: stableHeaders });
    if (res.ok || res.status === 404) {
      showToast("广告栏位已删除");
      await loadAds();
    } else {
      setError(`删除失败 (${res.status})`);
    }
  };

  // -------------------------------------------------------------- relays --
  const [relays, setRelays] = useState<RelayStationAdmin[]>([]);
  const [loadingRelays, setLoadingRelays] = useState(false);
  const [relayDraft, setRelayDraft] = useState<RelayDraft>({ ...EMPTY_RELAY, supported_models_text: "", tags_text: "" });
  const [editingRelayId, setEditingRelayId] = useState<number | null>(null);
  const [relayFormOpen, setRelayFormOpen] = useState(false);
  const [savingRelay, setSavingRelay] = useState(false);
  const [relayError, setRelayError] = useState("");

  const loadRelays = useCallback(async () => {
    setLoadingRelays(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/relays`, { credentials: "include", headers: stableHeaders });
      if (!res.ok) throw new Error(`读取中转站失败 (${res.status})`);
      setRelays((await res.json()) as RelayStationAdmin[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "读取中转站失败");
    } finally {
      setLoadingRelays(false);
    }
  }, [apiBase, stableHeaders]);

  const openRelayForm = (station?: RelayStationAdmin) => {
    setRelayError("");
    if (station) {
      setEditingRelayId(station.id);
      setRelayDraft({
        name: station.name,
        url: station.url,
        tagline: station.tagline,
        description: station.description,
        price_note: station.price_note,
        billing_note: station.billing_note,
        is_sponsored: station.is_sponsored,
        is_enabled: station.is_enabled,
        sort_order: station.sort_order,
        supported_models_text: station.supported_models.join(", "),
        tags_text: station.tags.join(", "),
      });
    } else {
      setEditingRelayId(null);
      setRelayDraft({ ...EMPTY_RELAY, supported_models_text: "", tags_text: "" });
    }
    setRelayFormOpen(true);
  };

  const submitRelay = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!relayDraft.name.trim()) {
      setRelayError("请填写中转站名称。");
      return;
    }
    if (relayDraft.url && !/^https:\/\/\S+$/i.test(relayDraft.url.trim())) {
      setRelayError("站点地址必须是公开 HTTPS 地址。");
      return;
    }
    setSavingRelay(true);
    setRelayError("");
    try {
      const { supported_models_text, tags_text, ...rest } = relayDraft;
      const body: RelayStationInput = {
        ...rest,
        supported_models: splitList(supported_models_text),
        tags: splitList(tags_text),
      };
      const isEdit = editingRelayId !== null;
      const res = await fetch(`${apiBase}/api/v1/admin/relays${isEdit ? `/${editingRelayId}` : ""}`, {
        method: isEdit ? "PATCH" : "POST",
        credentials: "include",
        headers: jsonHeaders,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(errorDetail(payload, `保存失败 (${res.status})`));
      }
      showToast(isEdit ? "中转站已更新" : "中转站已添加");
      setRelayFormOpen(false);
      await loadRelays();
    } catch (e) {
      setRelayError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingRelay(false);
    }
  };

  const toggleRelay = async (station: RelayStationAdmin) => {
    const res = await fetch(`${apiBase}/api/v1/admin/relays/${station.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: jsonHeaders,
      body: JSON.stringify({ is_enabled: !station.is_enabled }),
    });
    if (res.ok) {
      showToast(station.is_enabled ? "已下线该中转站" : "已上线该中转站");
      await loadRelays();
    } else {
      setError(`更新失败 (${res.status})`);
    }
  };

  const deleteRelay = async (station: RelayStationAdmin) => {
    if (!window.confirm(`确定删除中转站「${station.name}」？`)) return;
    const res = await fetch(`${apiBase}/api/v1/admin/relays/${station.id}`, { method: "DELETE", credentials: "include", headers: stableHeaders });
    if (res.ok || res.status === 404) {
      showToast("中转站已删除");
      await loadRelays();
    } else {
      setError(`删除失败 (${res.status})`);
    }
  };

  useEffect(() => {
    void loadAds();
    void loadRelays();
  }, [loadAds, loadRelays]);

  const liveAdCount = ads.filter((slot) => adStatus(slot).label === "投放中").length;
  const liveRelayCount = relays.filter((station) => station.is_enabled).length;

  return (
    <div className="space-y-6">
      {toast ? (
        <div role="status" className="flex items-center justify-between rounded-[9px] border border-[color:var(--success)]/25 bg-[color:var(--success-soft)] p-4 text-sm font-medium text-[color:var(--success)]">
          <span>{toast}</span>
          <button type="button" onClick={() => setToast("")} className="ml-2 text-xs underline hover:opacity-80">关闭</button>
        </div>
      ) : null}
      {error ? <p role="alert" className="rounded-[9px] border border-[color:var(--danger)]/25 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger)]">{error}</p> : null}

      {/* Global switches */}
      <section className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-[14px] border border-[color:var(--line)] bg-[color:var(--panel)] p-4">
          <div className="flex items-center gap-2.5">
            <Megaphone size={18} weight="bold" className="text-amber-600" />
            <h3 className="text-sm font-semibold">广告栏位总开关</h3>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${adSlotsEnabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)]"}`}>
              {adSlotsEnabled ? "已开启" : "已关闭"}
            </span>
          </div>
          <p className="text-xs leading-5 text-[color:var(--muted)]">
            关闭后前台所有栏位立即隐藏，不影响已配置的广告记录。当前 {ads.length} 条广告，其中 {liveAdCount} 条在投放期内。
          </p>
          <button
            type="button"
            disabled={togglingSetting}
            onClick={() => onToggleSetting("ad_slots_enabled", !adSlotsEnabled)}
            className={`tactile mt-auto inline-flex min-h-10 items-center justify-center self-start rounded-[10px] px-5 text-xs font-semibold transition-all ${adSlotsEnabled ? "border border-[color:var(--danger)] text-[color:var(--danger)] hover:bg-[color:var(--danger-soft)]" : "bg-[color:var(--ink)] text-white hover:opacity-90"} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {adSlotsEnabled ? "关闭全部广告栏位" : "开启广告栏位"}
          </button>
        </div>
        <div className="flex flex-col gap-3 rounded-[14px] border border-[color:var(--line)] bg-[color:var(--panel)] p-4">
          <div className="flex items-center gap-2.5">
            <ArrowsLeftRight size={18} weight="bold" className="text-[color:var(--info)]" />
            <h3 className="text-sm font-semibold">中转站专区开关</h3>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${relayHubEnabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)]"}`}>
              {relayHubEnabled ? "已开启" : "已关闭"}
            </span>
          </div>
          <p className="text-xs leading-5 text-[color:var(--muted)]">
            控制导航栏、品牌筛选中的「中转站」入口与 /relays 页面。当前 {relays.length} 个中转站，{liveRelayCount} 个已上线。
          </p>
          <button
            type="button"
            disabled={togglingSetting}
            onClick={() => onToggleSetting("relay_hub_enabled", !relayHubEnabled)}
            className={`tactile mt-auto inline-flex min-h-10 items-center justify-center self-start rounded-[10px] px-5 text-xs font-semibold transition-all ${relayHubEnabled ? "border border-[color:var(--danger)] text-[color:var(--danger)] hover:bg-[color:var(--danger-soft)]" : "bg-[color:var(--ink)] text-white hover:opacity-90"} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {relayHubEnabled ? "关闭中转站专区" : "开启中转站专区"}
          </button>
        </div>
      </section>

      {/* Sub tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[color:var(--line)] pb-3">
        {([
          ["ads", "广告栏位", ads.length],
          ["relays", "中转站", relays.length],
        ] as const).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSubTab(id)}
            aria-current={subTab === id ? "page" : undefined}
            className={`tactile inline-flex items-center gap-2 rounded-[9px] px-3.5 py-2 text-xs font-semibold ${subTab === id ? "bg-[color:var(--ink)] text-white" : "border border-[color:var(--line-strong)]/60 bg-[color:var(--panel)] text-[color:var(--muted)] hover:text-[color:var(--ink)]"}`}
          >
            {label}
            <span className="mono text-[10px] opacity-70">{count}</span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => (subTab === "ads" ? loadAds() : loadRelays())}
          disabled={loadingAds || loadingRelays}
          className="button-secondary tactile ml-auto !min-h-9 !px-3 text-xs disabled:opacity-50"
        >
          <ArrowClockwise size={15} />刷新
        </button>
      </div>

      {/* ---------------------------------------------------------- Ads --- */}
      {subTab === "ads" ? (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4">
            <div>
              <h2 className="text-base font-semibold">广告栏位</h2>
              <p className="mt-0.5 text-xs text-black/55">按栏位投放，可设置排序、上下线时间；前台一律带「广告 / 赞助」标识，链接仅接受站内路径或公开 HTTPS 地址。</p>
            </div>
            <button type="button" onClick={() => openAdForm()} className="button-primary tactile !min-h-9 !px-3.5 text-xs"><Plus size={15} />新增广告</button>
          </div>

          {adFormOpen ? (
            <form onSubmit={submitAd} className="space-y-4 border-b border-[color:var(--line)] bg-[color:var(--subtle)]/40 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{editingAdId !== null ? `编辑广告 #${editingAdId}` : "新增广告"}</h3>
                <button type="button" onClick={() => setAdFormOpen(false)} className="text-xs text-[color:var(--muted)] hover:text-[color:var(--ink)]"><X size={16} /></button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <label className="text-xs font-medium text-black/70">投放栏位
                  <select value={adDraft.placement} onChange={(e) => setAdDraft((d) => ({ ...d, placement: e.target.value as AdPlacement }))} className="field mt-1 text-sm">
                    {AD_PLACEMENTS.map((placement) => <option key={placement} value={placement}>{AD_PLACEMENT_LABELS[placement].label}</option>)}
                  </select>
                  <span className="mt-1 block text-[11px] font-normal text-[color:var(--muted)]">{AD_PLACEMENT_LABELS[adDraft.placement].hint}</span>
                </label>
                <label className="text-xs font-medium text-black/70">标题 *
                  <input type="text" required maxLength={120} value={adDraft.title} onChange={(e) => setAdDraft((d) => ({ ...d, title: e.target.value }))} placeholder="例如：XX 中转站 · 新用户送 $5 额度" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">赞助方名称
                  <input type="text" maxLength={100} value={adDraft.sponsor_name} onChange={(e) => setAdDraft((d) => ({ ...d, sponsor_name: e.target.value }))} placeholder="展示在角标旁" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70 sm:col-span-2 lg:col-span-3">说明文案
                  <textarea rows={2} maxLength={600} value={adDraft.description} onChange={(e) => setAdDraft((d) => ({ ...d, description: e.target.value }))} placeholder="一两句话说明优惠、适用人群或注意事项" className="mt-1 w-full rounded-[8px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-3 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">跳转链接
                  <input type="text" maxLength={1000} value={adDraft.link_url} onChange={(e) => setAdDraft((d) => ({ ...d, link_url: e.target.value }))} placeholder="https://… 或 /relays" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">图片地址（选填）
                  <input type="text" maxLength={1000} value={adDraft.image_url} onChange={(e) => setAdDraft((d) => ({ ...d, image_url: e.target.value }))} placeholder="https://…/banner.png 或 /brand/…" className="field mt-1 text-sm" />
                </label>
                <div className="grid grid-cols-3 gap-3">
                  <label className="text-xs font-medium text-black/70">角标
                    <input type="text" maxLength={20} value={adDraft.badge} onChange={(e) => setAdDraft((d) => ({ ...d, badge: e.target.value }))} className="field mt-1 text-sm" />
                  </label>
                  <label className="text-xs font-medium text-black/70">按钮文案
                    <input type="text" maxLength={40} value={adDraft.cta_text} onChange={(e) => setAdDraft((d) => ({ ...d, cta_text: e.target.value }))} className="field mt-1 text-sm" />
                  </label>
                  <label className="text-xs font-medium text-black/70">排序
                    <input type="number" min={0} max={100000} value={adDraft.sort_order} onChange={(e) => setAdDraft((d) => ({ ...d, sort_order: Number(e.target.value) || 0 }))} className="field mt-1 text-sm" />
                  </label>
                </div>
                <label className="text-xs font-medium text-black/70">上线时间（选填）
                  <input type="datetime-local" value={toDatetimeLocal(adDraft.starts_at)} onChange={(e) => setAdDraft((d) => ({ ...d, starts_at: fromDatetimeLocal(e.target.value) }))} className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">下线时间（选填）
                  <input type="datetime-local" value={toDatetimeLocal(adDraft.ends_at)} onChange={(e) => setAdDraft((d) => ({ ...d, ends_at: fromDatetimeLocal(e.target.value) }))} className="field mt-1 text-sm" />
                </label>
                <label className="flex items-center gap-2 self-end pb-2 text-sm">
                  <input type="checkbox" checked={adDraft.is_enabled} onChange={(e) => setAdDraft((d) => ({ ...d, is_enabled: e.target.checked }))} className="h-5 w-5 accent-[color:var(--brand-strong)]" />启用
                </label>
              </div>
              {adError ? <p role="alert" className="text-sm text-[color:var(--danger)]">{adError}</p> : null}
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={savingAd} className="button-primary tactile !min-h-9 !px-4 text-xs disabled:opacity-50">{savingAd ? "正在保存…" : "保存"}</button>
                <button type="button" onClick={() => setAdFormOpen(false)} className="button-secondary tactile !min-h-9 !px-4 text-xs">取消</button>
              </div>
            </form>
          ) : null}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[color:var(--subtle)]/60 text-xs text-[color:var(--muted)]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">栏位</th>
                  <th className="px-4 py-2.5 font-medium">广告</th>
                  <th className="px-4 py-2.5 font-medium">投放期</th>
                  <th className="px-4 py-2.5 font-medium text-right">排序</th>
                  <th className="px-4 py-2.5 font-medium text-right">点击</th>
                  <th className="px-4 py-2.5 font-medium">状态</th>
                  <th className="px-4 py-2.5 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--line)]">
                {ads.map((slot) => {
                  const status = adStatus(slot);
                  const placement = AD_PLACEMENT_LABELS[slot.placement as AdPlacement];
                  return (
                    <tr key={slot.id} className={slot.is_enabled ? "" : "opacity-60"}>
                      <td className="px-4 py-3 align-top text-xs">{placement?.label || slot.placement}</td>
                      <td className="px-4 py-3 align-top">
                        <p className="font-semibold">{slot.title}</p>
                        <p className="mt-0.5 text-xs text-[color:var(--muted)]">
                          <span className="ad-badge mr-1.5">{slot.badge || "广告"}</span>
                          {slot.sponsor_name || "—"}
                        </p>
                        {slot.link_url ? (
                          <a href={slot.link_url} target="_blank" rel="noreferrer nofollow" className="mt-1 inline-flex max-w-[360px] items-center gap-1 truncate text-xs text-[color:var(--info)] hover:underline">
                            {slot.link_url}<ArrowSquareOut size={12} />
                          </a>
                        ) : <p className="mt-1 text-xs text-[color:var(--muted)]">未设置链接</p>}
                      </td>
                      <td className="px-4 py-3 align-top text-xs text-[color:var(--muted)]">
                        <p>{slot.starts_at ? formatTime(slot.starts_at) : "立即"}</p>
                        <p>→ {slot.ends_at ? formatTime(slot.ends_at) : "长期"}</p>
                      </td>
                      <td className="mono px-4 py-3 text-right align-top text-xs">{slot.sort_order}</td>
                      <td className="mono px-4 py-3 text-right align-top text-xs">{slot.click_count}</td>
                      <td className="px-4 py-3 align-top">
                        <span className={`status-pill ${status.tone === "success" ? "status-success" : status.tone === "warning" ? "status-warning" : status.tone === "info" ? "status-info" : ""}`}>{status.label}</span>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <div className="flex justify-end gap-1.5">
                          <button type="button" onClick={() => openAdForm(slot)} title="编辑" className="button-secondary tactile !min-h-8 !px-2.5 text-xs"><PencilSimple size={14} /></button>
                          <button type="button" onClick={() => toggleAd(slot)} title={slot.is_enabled ? "停用" : "启用"} className="button-secondary tactile !min-h-8 !px-2.5 text-xs">{slot.is_enabled ? <EyeSlash size={14} /> : <Eye size={14} />}</button>
                          <button type="button" onClick={() => deleteAd(slot)} title="删除" className="button-danger tactile !min-h-8 !px-2.5 text-xs"><Trash size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {ads.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-[color:var(--muted)]">{loadingAds ? "正在读取…" : "还没有广告栏位。点击「新增广告」开始配置。"}</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {/* -------------------------------------------------------- Relays --- */}
      {subTab === "relays" ? (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4">
            <div>
              <h2 className="text-base font-semibold">中转站</h2>
              <p className="mt-0.5 text-xs text-black/55">展示在「中转站」平台专区（/relays）。赞助站点排在前面并带「赞助」标识；站点地址仅接受公开 HTTPS。</p>
            </div>
            <button type="button" onClick={() => openRelayForm()} className="button-primary tactile !min-h-9 !px-3.5 text-xs"><Plus size={15} />添加中转站</button>
          </div>

          {relayFormOpen ? (
            <form onSubmit={submitRelay} className="space-y-4 border-b border-[color:var(--line)] bg-[color:var(--subtle)]/40 p-5">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{editingRelayId !== null ? `编辑中转站 #${editingRelayId}` : "添加中转站"}</h3>
                <button type="button" onClick={() => setRelayFormOpen(false)} className="text-xs text-[color:var(--muted)] hover:text-[color:var(--ink)]"><X size={16} /></button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <label className="text-xs font-medium text-black/70">名称 *
                  <input type="text" required maxLength={100} value={relayDraft.name} onChange={(e) => setRelayDraft((d) => ({ ...d, name: e.target.value }))} placeholder="例如：XX API 中转" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">站点地址（HTTPS）
                  <input type="text" maxLength={1000} value={relayDraft.url} onChange={(e) => setRelayDraft((d) => ({ ...d, url: e.target.value }))} placeholder="https://api.example.com" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">一句话简介
                  <input type="text" maxLength={160} value={relayDraft.tagline} onChange={(e) => setRelayDraft((d) => ({ ...d, tagline: e.target.value }))} placeholder="例如：OpenAI / Claude / Gemini 统一接入" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70 sm:col-span-2 lg:col-span-3">详细说明
                  <textarea rows={3} maxLength={2000} value={relayDraft.description} onChange={(e) => setRelayDraft((d) => ({ ...d, description: e.target.value }))} placeholder="接入方式、余额有效期、倍率、退款规则等对购买决策有用的信息" className="mt-1 w-full rounded-[8px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-3 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70 sm:col-span-2">支持的模型（逗号或换行分隔，最多 40 个）
                  <textarea rows={2} value={relayDraft.supported_models_text} onChange={(e) => setRelayDraft((d) => ({ ...d, supported_models_text: e.target.value }))} placeholder="gpt-4.1, claude-sonnet-4, gemini-2.5-pro" className="mono mt-1 w-full rounded-[8px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-3 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">特性标签（逗号分隔，最多 12 个）
                  <input type="text" value={relayDraft.tags_text} onChange={(e) => setRelayDraft((d) => ({ ...d, tags_text: e.target.value }))} placeholder="支持支付宝, 余额不过期" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">价格说明
                  <input type="text" maxLength={200} value={relayDraft.price_note} onChange={(e) => setRelayDraft((d) => ({ ...d, price_note: e.target.value }))} placeholder="例如：官方价 0.7 折起 / $1 = ¥5" className="field mt-1 text-sm" />
                </label>
                <label className="text-xs font-medium text-black/70">计费方式
                  <input type="text" maxLength={120} value={relayDraft.billing_note} onChange={(e) => setRelayDraft((d) => ({ ...d, billing_note: e.target.value }))} placeholder="例如：按量计费 / 包月套餐" className="field mt-1 text-sm" />
                </label>
                <div className="flex flex-wrap items-end gap-4">
                  <label className="text-xs font-medium text-black/70">排序
                    <input type="number" min={0} max={100000} value={relayDraft.sort_order} onChange={(e) => setRelayDraft((d) => ({ ...d, sort_order: Number(e.target.value) || 0 }))} className="field mt-1 w-24 text-sm" />
                  </label>
                  <label className="flex items-center gap-2 pb-2 text-sm">
                    <input type="checkbox" checked={relayDraft.is_sponsored} onChange={(e) => setRelayDraft((d) => ({ ...d, is_sponsored: e.target.checked }))} className="h-5 w-5 accent-[color:var(--brand-strong)]" />赞助（置顶并标识）
                  </label>
                  <label className="flex items-center gap-2 pb-2 text-sm">
                    <input type="checkbox" checked={relayDraft.is_enabled} onChange={(e) => setRelayDraft((d) => ({ ...d, is_enabled: e.target.checked }))} className="h-5 w-5 accent-[color:var(--brand-strong)]" />上线
                  </label>
                </div>
              </div>
              {relayError ? <p role="alert" className="text-sm text-[color:var(--danger)]">{relayError}</p> : null}
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={savingRelay} className="button-primary tactile !min-h-9 !px-4 text-xs disabled:opacity-50">{savingRelay ? "正在保存…" : "保存"}</button>
                <button type="button" onClick={() => setRelayFormOpen(false)} className="button-secondary tactile !min-h-9 !px-4 text-xs">取消</button>
              </div>
            </form>
          ) : null}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[color:var(--subtle)]/60 text-xs text-[color:var(--muted)]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">中转站</th>
                  <th className="px-4 py-2.5 font-medium">模型 / 标签</th>
                  <th className="px-4 py-2.5 font-medium">价格 / 计费</th>
                  <th className="px-4 py-2.5 font-medium text-right">排序</th>
                  <th className="px-4 py-2.5 font-medium text-right">点击</th>
                  <th className="px-4 py-2.5 font-medium">状态</th>
                  <th className="px-4 py-2.5 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--line)]">
                {relays.map((station) => (
                  <tr key={station.id} className={station.is_enabled ? "" : "opacity-60"}>
                    <td className="px-4 py-3 align-top">
                      <p className="flex items-center gap-2 font-semibold">{station.name}{station.is_sponsored ? <span className="ad-badge">赞助</span> : null}</p>
                      {station.tagline ? <p className="mt-0.5 text-xs text-[color:var(--muted)]">{station.tagline}</p> : null}
                      {station.url ? (
                        <a href={station.url} target="_blank" rel="noreferrer nofollow" className="mt-1 inline-flex max-w-[320px] items-center gap-1 truncate text-xs text-[color:var(--info)] hover:underline">{station.url}<ArrowSquareOut size={12} /></a>
                      ) : <p className="mt-1 text-xs text-[color:var(--muted)]">未设置地址</p>}
                    </td>
                    <td className="px-4 py-3 align-top text-xs">
                      <p className="mono text-[color:var(--muted)]">{station.supported_models.slice(0, 4).join(", ") || "—"}{station.supported_models.length > 4 ? ` +${station.supported_models.length - 4}` : ""}</p>
                      {station.tags.length > 0 ? <p className="mt-1 flex flex-wrap gap-1">{station.tags.map((tag) => <span key={tag} className="relay-chip">{tag}</span>)}</p> : null}
                    </td>
                    <td className="px-4 py-3 align-top text-xs">
                      <p>{station.price_note || "—"}</p>
                      <p className="text-[color:var(--muted)]">{station.billing_note || ""}</p>
                    </td>
                    <td className="mono px-4 py-3 text-right align-top text-xs">{station.sort_order}</td>
                    <td className="mono px-4 py-3 text-right align-top text-xs">{station.click_count}</td>
                    <td className="px-4 py-3 align-top"><span className={`status-pill ${station.is_enabled ? "status-success" : ""}`}>{station.is_enabled ? "已上线" : "已下线"}</span></td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex justify-end gap-1.5">
                        <button type="button" onClick={() => openRelayForm(station)} title="编辑" className="button-secondary tactile !min-h-8 !px-2.5 text-xs"><PencilSimple size={14} /></button>
                        <button type="button" onClick={() => toggleRelay(station)} title={station.is_enabled ? "下线" : "上线"} className="button-secondary tactile !min-h-8 !px-2.5 text-xs">{station.is_enabled ? <EyeSlash size={14} /> : <Eye size={14} />}</button>
                        <button type="button" onClick={() => deleteRelay(station)} title="删除" className="button-danger tactile !min-h-8 !px-2.5 text-xs"><Trash size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {relays.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-[color:var(--muted)]">{loadingRelays ? "正在读取…" : "还没有中转站。点击「添加中转站」开始配置。"}</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
