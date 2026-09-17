"use client";

import { useEffect, useState } from "react";
import {
  ArrowClockwise,
  ArrowSquareOut,
  Check,
  CheckCircle,
  Copy,
  Gift,
  MagnifyingGlass,
  Plus,
  Sliders,
  Sparkle,
  Ticket,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import type {
  AdminCampaignCreate,
  AdminCouponImportRequest,
  AdminCouponImportResponse,
  AdminCouponPageOut,
  AdminCouponSettingsUpdate,
  AdminCouponStats,
  CampaignRead,
  ShopCoupon,
} from "@/lib/types";

export function CouponsAdminPanel({
  apiBase,
  headers,
}: {
  apiBase: string;
  headers: Record<string, string>;
}) {
  // Stats & Settings
  const [stats, setStats] = useState<AdminCouponStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [dropEnabled, setDropEnabled] = useState(true);
  const [dropProbability, setDropProbability] = useState(20);
  const [dynamicDrop, setDynamicDrop] = useState(true);
  const [dailyDropLimit, setDailyDropLimit] = useState(1);
  const [savingSettings, setSavingSettings] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  // Sub-tabs
  const [activeSubTab, setActiveSubTab] = useState<"inventory" | "campaigns">("inventory");

  // Platform shops for coupon/campaign binding
  const [platformShops, setPlatformShops] = useState<{ id: number; name: string; token: string; source_url: string }[]>([]);
  const [couponShopFilter, setCouponShopFilter] = useState<string>("all");

  // Coupon inventory
  const [coupons, setCoupons] = useState<ShopCoupon[]>([]);
  const [couponTotal, setCouponTotal] = useState(0);
  const [couponPage, setCouponPage] = useState(1);
  const [couponStatus, setCouponStatus] = useState<"all" | "unassigned" | "assigned" | "used">("all");
  const [couponSearch, setCouponSearch] = useState("");
  const [loadingCoupons, setLoadingCoupons] = useState(false);
  const [deletingCouponId, setDeletingCouponId] = useState<number | null>(null);

  // Campaigns
  const [campaigns, setCampaigns] = useState<CampaignRead[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [deletingCampaignId, setDeletingCampaignId] = useState<number | null>(null);

  // Modals
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importSelectedShopId, setImportSelectedShopId] = useState<string>("default");
  const [importForm, setImportForm] = useState({
    name: "专享立减券",
    discount_amount: 5,
    min_spend: 15,
    shop_id: 0,
    shop_name: "彩头AI",
    shop_url: "https://wzyp.cn/shop/pricememo",
    coupon_batch_id: 0,
    expires_days: 30,
    codes_text: "",
  });
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<AdminCouponImportResponse | null>(null);

  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [syncToken, setSyncToken] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<AdminCouponImportResponse | null>(null);

  const [isCampaignModalOpen, setIsCampaignModalOpen] = useState(false);
  const [campaignSelectedShopId, setCampaignSelectedShopId] = useState<string>("");
  const [campaignForm, setCampaignForm] = useState<AdminCampaignCreate & { expires_days: number }>({
    campaign_code: "",
    title: "",
    coupon_batch_id: 0,
    shop_id: null,
    shop_name: "",
    shop_url: "",
    max_per_user: 1,
    total_quota: 100,
    expires_days: 90,
  });
  const [creatingCampaign, setCreatingCampaign] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  };

  // Fetch Platform Shops
  const fetchPlatformShops = async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/shops`, { credentials: "include", headers });
      if (res.ok) {
        const data = await res.json();
        setPlatformShops(data);
        // If importForm default shop not found, set to first shop or default
        if (data.length > 0) {
          const defaultShop = data.find((s: any) => s.token === "pricememo") || data[0];
          setImportForm((prev) => ({
            ...prev,
            shop_id: defaultShop.id,
            shop_name: defaultShop.name,
            shop_url: defaultShop.source_url,
          }));
          setImportSelectedShopId(defaultShop.id.toString());
        }
      }
    } catch {
      // ignore
    }
  };

  // Fetch Stats
  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/stats`, { credentials: "include", headers });
      if (res.ok) {
        const data: AdminCouponStats = await res.json();
        setStats(data);
        setDropEnabled(data.drop_enabled);
        setDropProbability(data.drop_probability);
        setDynamicDrop(data.dynamic_drop);
        setDailyDropLimit(data.daily_drop_limit);
      }
    } catch {
      // ignore
    } finally {
      setLoadingStats(false);
    }
  };

  // Save Settings
  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const payload: AdminCouponSettingsUpdate = {
        drop_enabled: dropEnabled,
        drop_probability: dropProbability,
        dynamic_drop: dynamicDrop,
        daily_drop_limit: dailyDropLimit,
      };
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data: AdminCouponStats = await res.json();
        setStats(data);
        showToast("掉落配置更新成功");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`保存失败: ${err.detail || "未知错误"}`);
      }
    } catch (e: any) {
      showToast(`保存失败: ${e.message}`);
    } finally {
      setSavingSettings(false);
    }
  };

  // Fetch Coupons Page
  const fetchCoupons = async (page = couponPage) => {
    setLoadingCoupons(true);
    try {
      const q = new URLSearchParams({
        page: page.toString(),
        page_size: "20",
        status: couponStatus,
      });
      if (couponShopFilter !== "all") {
        q.set("shop_id", couponShopFilter);
      }
      if (couponSearch.trim()) {
        q.set("search", couponSearch.trim());
      }
      const res = await fetch(`${apiBase}/api/v1/admin/coupons?${q.toString()}`, {
        credentials: "include",
        headers,
      });
      if (res.ok) {
        const data: AdminCouponPageOut = await res.json();
        // Deleting the last row of the last page leaves the fetch on an empty
        // page; fall back to the new last page instead of showing nothing.
        if (data.items.length === 0 && data.total > 0 && page > 1) {
          const lastPage = Math.max(1, Math.ceil(data.total / (data.page_size || 50)));
          if (lastPage !== page) {
            setLoadingCoupons(false);
            await fetchCoupons(Math.min(page, lastPage));
            return;
          }
        }
        setCoupons(data.items);
        setCouponTotal(data.total);
        setCouponPage(data.page);
      }
    } catch {
      // ignore
    } finally {
      setLoadingCoupons(false);
    }
  };

  // Fetch Campaigns
  const fetchCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/campaigns`, {
        credentials: "include",
        headers,
      });
      if (res.ok) {
        const data: CampaignRead[] = await res.json();
        setCampaigns(data);
      }
    } catch {
      // ignore
    } finally {
      setLoadingCampaigns(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchPlatformShops();
  }, []);

  useEffect(() => {
    if (activeSubTab === "inventory") {
      fetchCoupons(1);
    } else {
      fetchCampaigns();
    }
  }, [activeSubTab, couponStatus, couponShopFilter]);

  // Delete Coupon
  const handleDeleteCoupon = async (id: number) => {
    if (!window.confirm(`确定要删除此优惠券（ID #${id}）吗？删除后将无法找回。`)) return;
    setDeletingCouponId(id);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers,
      });
      if (res.ok) {
        showToast(`券 #${id} 已成功删除`);
        fetchCoupons(couponPage);
        fetchStats();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`删除失败: ${err.detail || "操作不允许"}`);
      }
    } catch (e: any) {
      showToast(`删除失败: ${e.message}`);
    } finally {
      setDeletingCouponId(null);
    }
  };

  // Delete Campaign
  const handleDeleteCampaign = async (id: number, code: string) => {
    if (!window.confirm(`确定要删除活动口令【${code}】吗？`)) return;
    setDeletingCampaignId(id);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/campaigns/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers,
      });
      if (res.ok) {
        showToast(`口令【${code}】已删除`);
        fetchCampaigns();
        fetchStats();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`删除失败: ${err.detail || "操作不允许"}`);
      }
    } catch (e: any) {
      showToast(`删除失败: ${e.message}`);
    } finally {
      setDeletingCampaignId(null);
    }
  };

  // Submit Import
  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Coupons without a resolvable shop fall into the site-wide pool on
    // redemption, so require either a platform shop or a valid link.
    if (!importForm.shop_id && !importForm.shop_url?.trim()) {
      setImportResult({
        success: false,
        imported_count: 0,
        skipped_count: 0,
        message: "请选择平台店铺，或填写有效店铺链接后再导入。",
      });
      return;
    }
    if (importForm.shop_url?.trim() && !/^https?:\/\/\S+$/i.test(importForm.shop_url.trim())) {
      setImportResult({
        success: false,
        imported_count: 0,
        skipped_count: 0,
        message: "店铺链接必须是有效的 http(s) 地址。",
      });
      return;
    }
    setImporting(true);
    setImportResult(null);
    try {
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + Number(importForm.expires_days || 30));

      const payload: AdminCouponImportRequest = {
        name: importForm.name,
        discount_amount: Number(importForm.discount_amount),
        min_spend: Number(importForm.min_spend),
        shop_id: importForm.shop_id > 0 ? importForm.shop_id : null,
        shop_name: importForm.shop_name,
        shop_url: importForm.shop_url,
        coupon_batch_id: Number(importForm.coupon_batch_id || 0),
        expires_at: expiresAt.toISOString(),
        codes_text: importForm.codes_text,
      };

      const res = await fetch(`${apiBase}/api/v1/admin/coupons/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      const data: AdminCouponImportResponse = await res.json();
      if (res.ok) {
        setImportResult(data);
        setImportForm((prev) => ({ ...prev, codes_text: "" }));
        fetchStats();
        fetchCoupons(1);
      } else {
        setImportResult({
          success: false,
          imported_count: 0,
          skipped_count: 0,
          message: (data as any).detail || "导入失败，请检查输入",
        });
      }
    } catch (err: any) {
      setImportResult({
        success: false,
        imported_count: 0,
        skipped_count: 0,
        message: err.message || "请求异常",
      });
    } finally {
      setImporting(false);
    }
  };

  // Submit LDXP Sync
  const handleSyncLdxp = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      // The merchant token goes in the body, never the URL, so it cannot leak
      // into reverse-proxy or access logs.
      const res = await fetch(`${apiBase}/api/v1/admin/coupons/sync-ldxp`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ token: syncToken.trim() }),
      });
      const data: AdminCouponImportResponse = await res.json();
      if (res.ok) {
        setSyncResult(data);
        fetchStats();
        fetchCoupons(1);
      } else {
        setSyncResult({
          success: false,
          imported_count: 0,
          skipped_count: 0,
          message: (data as any).detail || "同步失败",
        });
      }
    } catch (err: any) {
      setSyncResult({
        success: false,
        imported_count: 0,
        skipped_count: 0,
        message: err.message || "同步异常",
      });
    } finally {
      setSyncing(false);
    }
  };

  // Submit Create Campaign
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignForm.shop_id && !campaignForm.shop_url && !campaignForm.shop_name) {
      alert("必须选择或输入该活动口令归属的店铺！券是跟着店铺走的。");
      return;
    }
    // A custom shop that cannot be resolved server-side would produce a
    // shop-less campaign whose redemptions fall back to the site-wide pool.
    // Require a link so the binding can always be resolved by URL.
    if (!campaignForm.shop_id && !campaignForm.shop_url?.trim()) {
      alert("手动指定的店铺必须填写店铺链接，否则无法确定发券范围。");
      return;
    }
    if (campaignForm.shop_url?.trim() && !/^https?:\/\/\S+$/i.test(campaignForm.shop_url.trim())) {
      alert("店铺链接必须是有效的 http(s) 地址。");
      return;
    }
    setCreatingCampaign(true);
    try {
      const expiresAt = new Date();
      expiresAt.setDate(expiresAt.getDate() + Number(campaignForm.expires_days || 90));

      const payload = {
        campaign_code: campaignForm.campaign_code.trim(),
        title: campaignForm.title.trim(),
        coupon_batch_id: Number(campaignForm.coupon_batch_id || 0),
        shop_id: campaignForm.shop_id || null,
        shop_name: campaignForm.shop_name || null,
        shop_url: campaignForm.shop_url || null,
        max_per_user: Number(campaignForm.max_per_user || 1),
        total_quota: Number(campaignForm.total_quota || 100),
        expires_at: expiresAt.toISOString(),
      };

      const res = await fetch(`${apiBase}/api/v1/admin/coupons/campaigns`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        showToast("活动口令创建成功");
        setIsCampaignModalOpen(false);
        setCampaignSelectedShopId("");
        setCampaignForm({
          campaign_code: "",
          title: "",
          coupon_batch_id: 0,
          shop_id: null,
          shop_name: "",
          shop_url: "",
          max_per_user: 1,
          total_quota: 100,
          expires_days: 90,
        });
        fetchStats();
        fetchCampaigns();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`创建失败: ${err.detail || "参数错误"}`);
      }
    } catch (err: any) {
      alert(`创建失败: ${err.message}`);
    } finally {
      setCreatingCampaign(false);
    }
  };

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const getStockStatusBadge = (stock: number) => {
    if (stock <= 0) {
      return (
        <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-bold text-rose-700">
          已耗尽
        </span>
      );
    }
    if (stock < 5) {
      return (
        <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-bold text-red-700">
          极度紧缺 ({stock})
        </span>
      );
    }
    if (stock < 20) {
      return (
        <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-bold text-amber-700">
          库存偏低 ({stock})
        </span>
      );
    }
    return (
      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
        充足 ({stock})
      </span>
    );
  };

  return (
    <div className="space-y-8">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-5 right-5 z-50 rounded-xl bg-[color:var(--ink)] px-4 py-2.5 text-xs font-semibold text-white shadow-lg animate-in fade-in slide-in-from-top-3 duration-200 flex items-center gap-2">
          <CheckCircle size={16} weight="fill" className="text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* 1. Metric Overview Cards */}
      <section className="data-strip sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <div className="data-cell">
          <div className="flex items-center justify-between">
            <p className="data-label">可掉落库存</p>
            {stats && getStockStatusBadge(stats.unassigned_coupons)}
          </div>
          <p className="data-value text-amber-600">{stats?.unassigned_coupons ?? "-"}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">已发放/领取</p>
          <p className="data-value">{stats?.assigned_coupons ?? "-"}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">已核销使用</p>
          <p className="data-value text-emerald-600">{stats?.used_coupons ?? "-"}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">总券码总量</p>
          <p className="data-value">{stats?.total_coupons ?? "-"}</p>
        </div>
        <div className="data-cell">
          <p className="data-label">活动口令</p>
          <p className="data-value">{stats?.total_campaigns ?? "-"}</p>
        </div>
        <div className="data-cell">
          <div className="flex items-center justify-between">
            <p className="data-label">掉落状态</p>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                stats?.drop_enabled ? "bg-emerald-500/15 text-emerald-700" : "bg-zinc-500/15 text-zinc-600"
              }`}
            >
              {stats?.drop_enabled ? "进行中" : "已暂停"}
            </span>
          </div>
          <p className="data-value font-mono">
            {stats ? (stats.drop_enabled ? `${stats.drop_probability}%` : "0%") : "-"}
          </p>
        </div>
      </section>

      {/* 2. Drop Policy & Limits Card */}
      <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
        <div className="flex flex-col gap-2 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sliders size={18} className="text-amber-600" weight="bold" />
              <h2 className="text-base font-semibold">前台掉落策略与限额配置</h2>
            </div>
            <p className="mt-0.5 text-xs text-black/55">
              控制访客浏览网页时惊喜彩蛋券的掉落逻辑、概率控制和防刷限制。修改后实时生效。
            </p>
          </div>
          <button
            type="button"
            onClick={fetchStats}
            disabled={loadingStats}
            className="tactile inline-flex items-center gap-1 rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-1.5 text-xs font-medium text-[color:var(--foreground)] hover:bg-[color:var(--hover)] shrink-0 self-start sm:self-auto"
          >
            <ArrowClockwise size={13} className={loadingStats ? "animate-spin" : ""} />
            <span>刷新数据</span>
          </button>
        </div>

        <div className="p-5 space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Switch 1: drop_enabled */}
            <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-[color:var(--ink)]">允许前台随机掉落</h3>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      dropEnabled ? "bg-emerald-500/15 text-emerald-700" : "bg-zinc-500/15 text-zinc-600"
                    }`}
                  >
                    {dropEnabled ? "开启" : "关闭"}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-[color:var(--muted)]">
                  开启后，普通访客在浏览商品比价等页面 10 秒后，将有机会触发立减券掉落彩蛋弹窗。
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0 mt-1">
                <input
                  type="checkbox"
                  checked={dropEnabled}
                  onChange={(e) => setDropEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-zinc-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[color:var(--ink)]"></div>
              </label>
            </div>

            {/* Switch 2: dynamic_drop */}
            <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-[color:var(--ink)]">智能库存动态控频</h3>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      dynamicDrop ? "bg-blue-500/15 text-blue-700" : "bg-zinc-500/15 text-zinc-600"
                    }`}
                  >
                    {dynamicDrop ? "自适应" : "固定概率"}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-[color:var(--muted)]">
                  当可用券库存紧缺时自动降低掉落概率（库存 &lt; 20 张降至 15%，&lt; 5 张降至 5%），避免短时间被瞬间刷空。
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0 mt-1">
                <input
                  type="checkbox"
                  checked={dynamicDrop}
                  onChange={(e) => setDynamicDrop(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-zinc-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[color:var(--ink)]"></div>
              </label>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2 pt-2">
            {/* Slider: drop_probability */}
            <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[color:var(--ink)]">基准掉落概率</h3>
                  <p className="text-xs text-[color:var(--muted)] mt-0.5">
                    访客每次访问页面的基准中奖概率 (0% - 100%)
                  </p>
                </div>
                <span className="font-mono text-base font-black text-amber-600 px-2.5 py-0.5 rounded-lg bg-amber-50 border border-amber-200">
                  {dropProbability}%
                </span>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={dropProbability}
                  onChange={(e) => setDropProbability(Number(e.target.value))}
                  className="w-full accent-[color:var(--ink)] cursor-pointer"
                />
              </div>
              <div className="flex justify-between text-[11px] text-[color:var(--muted)]">
                <span>0% (不掉落)</span>
                <span>20% (推荐默认)</span>
                <span>50% (促销活动)</span>
                <span>100% (必出)</span>
              </div>
            </div>

            {/* Input: daily_drop_limit */}
            <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4 space-y-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-[color:var(--ink)]">全站每日掉落配额上限（止损兜底）</h3>
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    预算安全锁
                  </span>
                </div>
                <p className="text-xs text-[color:var(--muted)] mt-0.5">
                  全站每天最多发放的掉落券总张数。达到该上限后当天自动熔断停止掉落，次日恢复，防止资金过度补贴。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={dailyDropLimit}
                  onChange={(e) => setDailyDropLimit(Math.max(1, Number(e.target.value)))}
                  className="w-24 rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--panel)] px-3 py-1.5 font-mono text-sm text-[color:var(--ink)] focus:outline-none"
                />
                <span className="text-xs text-[color:var(--muted)]">张 / 天（达到即熔断）</span>
              </div>
              <p className="text-[11px] text-[color:var(--muted)]">
                🛡️ 底层双重风控：系统同时严格限制单个登录账号 24 小时内最多领取 1 张，双重防刷。
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end pt-2 border-t border-[color:var(--line)]">
            <button
              type="button"
              onClick={handleSaveSettings}
              disabled={savingSettings}
              className="tactile inline-flex items-center gap-1.5 rounded-[10px] bg-[color:var(--ink)] px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:opacity-90 active:scale-95 disabled:opacity-50"
            >
              {savingSettings ? <ArrowClockwise size={14} className="animate-spin" /> : <Check size={14} weight="bold" />}
              <span>{savingSettings ? "正在保存..." : "保存掉落设置"}</span>
            </button>
          </div>
        </div>
      </section>

      {/* 3. Sub-tabs Navigation & Operational Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--line)] pb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveSubTab("inventory")}
            className={`tactile inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2 text-xs font-semibold transition ${
              activeSubTab === "inventory"
                ? "bg-[color:var(--ink)] text-white shadow-sm"
                : "border border-[color:var(--line-strong)]/60 bg-[color:var(--panel)] text-[color:var(--muted)] hover:text-[color:var(--ink)]"
            }`}
          >
            <Ticket size={16} weight={activeSubTab === "inventory" ? "bold" : "regular"} />
            <span>券码库存明细</span>
            <span className="mono rounded-full bg-black/10 px-1.5 py-0.2 text-[10px]">
              {couponTotal}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab("campaigns")}
            className={`tactile inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2 text-xs font-semibold transition ${
              activeSubTab === "campaigns"
                ? "bg-[color:var(--ink)] text-white shadow-sm"
                : "border border-[color:var(--line-strong)]/60 bg-[color:var(--panel)] text-[color:var(--muted)] hover:text-[color:var(--ink)]"
            }`}
          >
            <Gift size={16} weight={activeSubTab === "campaigns" ? "bold" : "regular"} />
            <span>营销口令管理 (如 RADAR888)</span>
            <span className="mono rounded-full bg-black/10 px-1.5 py-0.2 text-[10px]">
              {campaigns.length}
            </span>
          </button>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setSyncResult(null);
              setIsSyncModalOpen(true);
            }}
            className="tactile inline-flex items-center gap-1.5 rounded-[10px] border hairline border-amber-500/40 bg-amber-50/50 px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100/70"
          >
            <Sparkle size={14} weight="fill" className="text-amber-600" />
            <span>一键同步 LDXP 券码</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setImportResult(null);
              setIsImportModalOpen(true);
            }}
            className="tactile inline-flex items-center gap-1.5 rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-xs font-semibold text-[color:var(--ink)] hover:bg-[color:var(--hover)]"
          >
            <Plus size={14} weight="bold" />
            <span>批量导入券码</span>
          </button>

          {activeSubTab === "campaigns" && (
            <button
              type="button"
              onClick={() => setIsCampaignModalOpen(true)}
              className="tactile inline-flex items-center gap-1.5 rounded-[10px] bg-[color:var(--ink)] px-3 py-2 text-xs font-semibold text-white shadow-sm hover:opacity-90"
            >
              <Plus size={14} weight="bold" />
              <span>新建营销口令</span>
            </button>
          )}
        </div>
      </div>

      {/* SUBTAB 1: 券码库存明细 */}
      {activeSubTab === "inventory" && (
        <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
          {/* Filter / Search Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--line)] bg-[color:var(--panel)] px-5 py-3 text-xs">
            <div className="flex items-center gap-2 overflow-x-auto">
              <div className="flex items-center gap-1.5">
                {[
                  { id: "all", label: "全部券码" },
                  { id: "unassigned", label: "待领取 / 可用" },
                  { id: "assigned", label: "已领入卡包" },
                  { id: "used", label: "已核销" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => {
                      setCouponStatus(tab.id as any);
                      setCouponPage(1);
                    }}
                    className={`rounded-lg px-2.5 py-1 font-medium transition ${
                      couponStatus === tab.id
                        ? "bg-[color:var(--ink)] text-white"
                        : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {platformShops.length > 0 && (
                <div className="flex items-center gap-1 pl-2 border-l border-[color:var(--line)]">
                  <span className="text-[color:var(--muted)] text-[11px]">店铺:</span>
                  <select
                    value={couponShopFilter}
                    onChange={(e) => {
                      setCouponShopFilter(e.target.value);
                      setCouponPage(1);
                    }}
                    className="rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-2 py-1 text-xs text-[color:var(--ink)] focus:outline-none"
                  >
                    <option value="all">全部店铺</option>
                    {platformShops.map((s) => (
                      <option key={s.id} value={s.id.toString()}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                setCouponPage(1);
                fetchCoupons(1);
              }}
              className="flex items-center gap-2"
            >
              <div className="relative">
                <MagnifyingGlass size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[color:var(--muted)]" />
                <input
                  type="text"
                  placeholder="搜索券码或名称..."
                  value={couponSearch}
                  onChange={(e) => setCouponSearch(e.target.value)}
                  className="rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] pl-8 pr-3 py-1 text-xs text-[color:var(--ink)] focus:outline-none w-48 sm:w-64"
                />
              </div>
              <button
                type="submit"
                className="tactile rounded-lg border hairline bg-[color:var(--panel)] px-2.5 py-1 text-xs font-medium text-[color:var(--foreground)] hover:bg-[color:var(--hover)]"
              >
                搜索
              </button>
              <button
                type="button"
                onClick={() => fetchCoupons(couponPage)}
                className="tactile rounded-lg border hairline bg-[color:var(--panel)] p-1 text-[color:var(--foreground)] hover:bg-[color:var(--hover)]"
                title="刷新列表"
              >
                <ArrowClockwise size={14} className={loadingCoupons ? "animate-spin" : ""} />
              </button>
            </form>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[color:var(--line)] bg-[color:var(--subtle)] text-[color:var(--muted)] font-medium">
                  <th className="px-4 py-3 w-16">ID</th>
                  <th className="px-4 py-3">券码 (兑换码)</th>
                  <th className="px-4 py-3">券名称</th>
                  <th className="px-4 py-3">面额 / 门槛</th>
                  <th className="px-4 py-3">归属店铺</th>
                  <th className="px-4 py-3">状态</th>
                  <th className="px-4 py-3">领取时间</th>
                  <th className="px-4 py-3">有效期至</th>
                  <th className="px-4 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--line)]">
                {coupons.length > 0 ? (
                  coupons.map((c) => {
                    const isExpired = new Date(c.expires_at).getTime() < Date.now();
                    return (
                      <tr key={c.id} className="hover:bg-[color:var(--hover)] transition">
                        <td className="px-4 py-3 mono text-[color:var(--muted)]">#{c.id}</td>
                        <td className="px-4 py-3">
                          <div className="inline-flex items-center gap-1.5">
                            <code className="rounded bg-[color:var(--subtle)] px-2 py-0.5 font-mono font-bold text-xs text-[color:var(--ink)]">
                              {c.code}
                            </code>
                            <button
                              type="button"
                              onClick={() => handleCopy(c.code)}
                              title="复制券码"
                              className="text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                            >
                              {copiedCode === c.code ? (
                                <Check size={13} className="text-emerald-600" />
                              ) : (
                                <Copy size={13} />
                              )}
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-semibold text-[color:var(--ink)]">{c.name}</td>
                        <td className="px-4 py-3">
                          <span className="font-bold text-amber-700">¥{c.discount_amount}</span>
                          <span className="text-[color:var(--muted)] ml-1">
                            (满 ¥{c.min_spend})
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {c.shop_url ? (
                            <a
                              href={c.shop_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[color:var(--ink)] hover:underline"
                            >
                              <span>{c.shop_name}</span>
                              <ArrowSquareOut size={11} className="text-[color:var(--muted)]" />
                            </a>
                          ) : (
                            <span>{c.shop_name}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {c.is_used ? (
                            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                              已核销
                            </span>
                          ) : c.is_assigned ? (
                            <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                              已存入卡包
                            </span>
                          ) : isExpired ? (
                            <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-[10px] font-bold text-zinc-600">
                              已过期
                            </span>
                          ) : (
                            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                              待领取 (可用)
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 mono text-[color:var(--muted)]">
                          {c.assigned_at
                            ? new Date(c.assigned_at).toLocaleString("zh-CN", { hour12: false })
                            : "-"}
                        </td>
                        <td className="px-4 py-3 mono text-[color:var(--muted)]">
                          {new Date(c.expires_at).toLocaleDateString("zh-CN")}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!c.is_assigned ? (
                            <button
                              type="button"
                              onClick={() => handleDeleteCoupon(c.id)}
                              disabled={deletingCouponId === c.id}
                              title="删除未领取的券"
                              className="tactile inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                            >
                              <Trash size={13} />
                              <span>删除</span>
                            </button>
                          ) : (
                            <span className="text-[11px] text-[color:var(--muted)]" title="已领取的券不可删除">
                              不可删
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-[color:var(--muted)]">
                      {loadingCoupons ? "正在加载券码列表..." : "暂无匹配的优惠券记录"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {couponTotal > 20 && (
            <div className="flex items-center justify-between border-t border-[color:var(--line)] px-5 py-3 text-xs">
              <span className="text-[color:var(--muted)]">
                共 {couponTotal} 条记录 · 第 {couponPage} / {Math.ceil(couponTotal / 20)} 页
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const prev = Math.max(1, couponPage - 1);
                    setCouponPage(prev);
                    fetchCoupons(prev);
                  }}
                  disabled={couponPage <= 1 || loadingCoupons}
                  className="tactile rounded-lg border hairline bg-[color:var(--panel)] px-3 py-1 text-xs font-medium disabled:opacity-40"
                >
                  上一页
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const next = couponPage + 1;
                    setCouponPage(next);
                    fetchCoupons(next);
                  }}
                  disabled={couponPage * 20 >= couponTotal || loadingCoupons}
                  className="tactile rounded-lg border hairline bg-[color:var(--panel)] px-3 py-1 text-xs font-medium disabled:opacity-40"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* SUBTAB 2: 营销口令管理 */}
      {activeSubTab === "campaigns" && (
        <section className="space-y-4">
          <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--subtle)] p-4 text-xs leading-6 text-[color:var(--ink)]">
            <p className="font-semibold text-sm">💡 什么是营销活动口令？</p>
            <p className="text-[color:var(--muted)] mt-1">
              类似于“邀请码/暗号福利”。例如您可以创建口令 <code className="font-mono font-bold text-amber-700 bg-amber-100/70 px-1.5 py-0.5 rounded">RADAR888</code> 或 <code className="font-mono font-bold text-amber-700 bg-amber-100/70 px-1.5 py-0.5 rounded">NEWYEAR2026</code>，将其发布在交流群或公告中。
              访客在个人中心（/account）输入口令后，即可直接领取一张对应批次的专享店铺立减券。
            </p>
          </div>

          <div className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="flex items-center justify-between border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-3">
              <span className="font-semibold text-xs text-[color:var(--ink)]">活动口令列表</span>
              <button
                type="button"
                onClick={fetchCampaigns}
                className="tactile rounded-lg border hairline bg-[color:var(--panel)] p-1 text-[color:var(--foreground)] hover:bg-[color:var(--hover)]"
              >
                <ArrowClockwise size={14} className={loadingCampaigns ? "animate-spin" : ""} />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[color:var(--line)] bg-[color:var(--subtle)] text-[color:var(--muted)] font-medium">
                    <th className="px-4 py-3">活动口令</th>
                    <th className="px-4 py-3">活动标题</th>
                    <th className="px-4 py-3">归属店铺</th>
                    <th className="px-4 py-3">关联券批次 ID</th>
                    <th className="px-4 py-3">单人限领</th>
                    <th className="px-4 py-3">领取进度 / 配额</th>
                    <th className="px-4 py-3">活动状态</th>
                    <th className="px-4 py-3">有效截止</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--line)]">
                  {campaigns.length > 0 ? (
                    campaigns.map((camp) => {
                      const isExpired = new Date(camp.expires_at).getTime() < Date.now();
                      const pct = camp.total_quota > 0 ? Math.min(100, Math.round((camp.claimed_count / camp.total_quota) * 100)) : 0;
                      return (
                        <tr key={camp.id} className="hover:bg-[color:var(--hover)] transition">
                          <td className="px-4 py-3">
                            <div className="inline-flex items-center gap-1.5">
                              <code className="rounded bg-amber-50 border border-amber-200 px-2 py-0.5 font-mono font-bold text-xs text-amber-900">
                                {camp.campaign_code}
                              </code>
                              <button
                                type="button"
                                onClick={() => handleCopy(camp.campaign_code)}
                                title="复制口令"
                                className="text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                              >
                                {copiedCode === camp.campaign_code ? (
                                  <Check size={13} className="text-emerald-600" />
                                ) : (
                                  <Copy size={13} />
                                )}
                              </button>
                            </div>
                          </td>
                          <td className="px-4 py-3 font-semibold text-[color:var(--ink)]">{camp.title}</td>
                          <td className="px-4 py-3">
                            {camp.shop_name ? (
                              camp.shop_url ? (
                                <a
                                  href={camp.shop_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-900 border border-amber-500/20 hover:underline"
                                >
                                  <span>{camp.shop_name}</span>
                                  <ArrowSquareOut size={10} className="text-amber-700" />
                                </a>
                              ) : (
                                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-900 border border-amber-500/20">
                                  {camp.shop_name}
                                </span>
                              )
                            ) : (
                              <span className="text-[color:var(--muted)]">未绑定</span>
                            )}
                          </td>
                          <td className="px-4 py-3 mono text-[color:var(--muted)]">
                            {camp.coupon_batch_id > 0 ? `批次 #${camp.coupon_batch_id}` : "全部未分配可用券"}
                          </td>
                          <td className="px-4 py-3">{camp.max_per_user} 张 / 人</td>
                          <td className="px-4 py-3">
                            <div className="space-y-1">
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="font-mono">
                                  {camp.claimed_count} / {camp.total_quota}
                                </span>
                                <span className="text-[color:var(--muted)]">{pct}%</span>
                              </div>
                              <div className="h-1.5 w-28 rounded-full bg-zinc-200 overflow-hidden">
                                <div className="h-full bg-amber-500 rounded-full" style={{ width: `${pct}%` }}></div>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            {isExpired ? (
                              <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-[10px] font-bold text-zinc-600">
                                已过期
                              </span>
                            ) : camp.is_active ? (
                              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                                生效中
                              </span>
                            ) : (
                              <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-[10px] font-bold text-zinc-600">
                                已关闭
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 mono text-[color:var(--muted)]">
                            {new Date(camp.expires_at).toLocaleDateString("zh-CN")}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteCampaign(camp.id, camp.campaign_code)}
                              disabled={deletingCampaignId === camp.id}
                              className="tactile inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                            >
                              <Trash size={13} />
                              <span>删除</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={9} className="py-12 text-center text-[color:var(--muted)]">
                        {loadingCampaigns ? "正在加载口令活动..." : "暂无活动口令，点击右上角新建"}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* MODAL 1: 批量导入券码 */}
      {isImportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/45 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-3">
              <div className="flex items-center gap-2">
                <Ticket size={20} className="text-amber-600" weight="bold" />
                <h3 className="text-base font-bold text-[color:var(--ink)]">批量导入店铺券码</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsImportModalOpen(false)}
                className="rounded-lg p-1 text-[color:var(--muted)] hover:bg-[color:var(--hover)] hover:text-[color:var(--ink)]"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleImportSubmit} className="space-y-4 overflow-y-auto pr-1 flex-1">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">优惠券名称</label>
                  <input
                    type="text"
                    required
                    value={importForm.name}
                    onChange={(e) => setImportForm({ ...importForm, name: e.target.value })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">关联批次 ID (可选)</label>
                  <input
                    type="number"
                    value={importForm.coupon_batch_id}
                    onChange={(e) => setImportForm({ ...importForm, coupon_batch_id: Number(e.target.value) })}
                    placeholder="0 表示默认通用批次"
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">面额 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={importForm.discount_amount}
                    onChange={(e) => setImportForm({ ...importForm, discount_amount: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">门槛 (满元可用)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={importForm.min_spend}
                    onChange={(e) => setImportForm({ ...importForm, min_spend: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">有效期 (天数)</label>
                  <input
                    type="number"
                    required
                    value={importForm.expires_days}
                    onChange={(e) => setImportForm({ ...importForm, expires_days: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">
                    选择归属店铺 (券跟着店铺走)
                  </label>
                  <select
                    value={importSelectedShopId}
                    onChange={(e) => {
                      const val = e.target.value;
                      setImportSelectedShopId(val);
                      if (val === "custom") {
                        setImportForm({ ...importForm, shop_id: 0, shop_name: "", shop_url: "" });
                      } else {
                        const s = platformShops.find((shop) => shop.id.toString() === val);
                        if (s) {
                          setImportForm({
                            ...importForm,
                            shop_id: s.id,
                            shop_name: s.name,
                            shop_url: s.source_url,
                          });
                        }
                      }
                    }}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none text-xs"
                  >
                    <option value="">-- 选择已有平台店铺 --</option>
                    {platformShops.map((s) => (
                      <option key={s.id} value={s.id.toString()}>
                        {s.name} ({s.token})
                      </option>
                    ))}
                    <option value="custom">✏️ 手动输入其他新店铺...</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block font-semibold mb-1 text-[color:var(--ink)]">所属店铺名</label>
                    <input
                      type="text"
                      required
                      value={importForm.shop_name}
                      onChange={(e) => setImportForm({ ...importForm, shop_name: e.target.value })}
                      className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold mb-1 text-[color:var(--ink)]">店铺直达链接</label>
                    <input
                      type="url"
                      required
                      value={importForm.shop_url}
                      onChange={(e) => setImportForm({ ...importForm, shop_url: e.target.value })}
                      className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="text-xs">
                <label className="block font-semibold mb-1 text-[color:var(--ink)]">
                  券码兑换码文本 (每行一条，或以逗号/分号分隔)
                </label>
                <textarea
                  required
                  rows={6}
                  placeholder="例如：
LDXP-ABCD-1234
LDXP-WXYZ-5678
..."
                  value={importForm.codes_text}
                  onChange={(e) => setImportForm({ ...importForm, codes_text: e.target.value })}
                  className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] p-3 font-mono text-xs focus:outline-none"
                />
              </div>

              {importResult && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    importResult.success
                      ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-800"
                      : "bg-rose-500/10 border border-rose-500/20 text-rose-800"
                  }`}
                >
                  {importResult.success ? (
                    <CheckCircle size={16} weight="fill" className="shrink-0" />
                  ) : (
                    <WarningCircle size={16} weight="fill" className="shrink-0" />
                  )}
                  <span>{importResult.message}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[color:var(--line)]">
                <button
                  type="button"
                  onClick={() => setIsImportModalOpen(false)}
                  className="button-secondary tactile px-4 py-2 text-xs rounded-lg"
                >
                  关闭
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  className="tactile inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--ink)] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50"
                >
                  {importing ? <ArrowClockwise size={13} className="animate-spin" /> : <Check size={13} weight="bold" />}
                  <span>{importing ? "正在导入..." : "确认导入"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: 链动小铺(LDXP)一键同步 */}
      {isSyncModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/45 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-3">
              <div className="flex items-center gap-2">
                <Sparkle size={18} className="text-amber-600" weight="fill" />
                <h3 className="text-base font-bold text-[color:var(--ink)]">同步链动小铺(LDXP)优惠券</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsSyncModalOpen(false)}
                className="rounded-lg p-1 text-[color:var(--muted)] hover:bg-[color:var(--hover)] hover:text-[color:var(--ink)]"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-[color:var(--muted)] leading-relaxed">
                系统将通过商户 API 密钥调用链动小铺接口，拉取店铺内有效的满减优惠券及兑换券码并自动入库排重。
              </p>

              <div>
                <label className="block font-semibold mb-1 text-[color:var(--ink)]">
                  商户 Token (可选，留空使用系统后台默认配置)
                </label>
                <input
                  type="text"
                  placeholder="留空默认使用商户密钥"
                  value={syncToken}
                  onChange={(e) => setSyncToken(e.target.value)}
                  className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2 font-mono text-xs focus:outline-none"
                />
              </div>

              {syncResult && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    syncResult.success
                      ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-800"
                      : "bg-rose-500/10 border border-rose-500/20 text-rose-800"
                  }`}
                >
                  {syncResult.success ? (
                    <CheckCircle size={16} weight="fill" className="shrink-0" />
                  ) : (
                    <WarningCircle size={16} weight="fill" className="shrink-0" />
                  )}
                  <span>{syncResult.message}</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[color:var(--line)]">
              <button
                type="button"
                onClick={() => setIsSyncModalOpen(false)}
                className="button-secondary tactile px-4 py-2 text-xs rounded-lg"
              >
                完成
              </button>
              <button
                type="button"
                onClick={handleSyncLdxp}
                disabled={syncing}
                className="tactile inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--ink)] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50"
              >
                <ArrowClockwise size={13} className={syncing ? "animate-spin" : ""} />
                <span>{syncing ? "同步请求中..." : "开始同步"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: 新建营销口令 */}
      {isCampaignModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/45 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-3">
              <div className="flex items-center gap-2">
                <Gift size={20} className="text-amber-600" weight="bold" />
                <h3 className="text-base font-bold text-[color:var(--ink)]">新建营销活动口令</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCampaignModalOpen(false)}
                className="rounded-lg p-1 text-[color:var(--muted)] hover:bg-[color:var(--hover)] hover:text-[color:var(--ink)]"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateCampaign} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold mb-1 text-[color:var(--ink)]">
                  活动口令 (暗号/兑换码，如 RADAR888)
                </label>
                <input
                  type="text"
                  required
                  placeholder="例如：RADAR888"
                  value={campaignForm.campaign_code}
                  onChange={(e) => setCampaignForm({ ...campaignForm, campaign_code: e.target.value.toUpperCase() })}
                  className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2 font-mono font-bold text-xs uppercase focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold mb-1 text-[color:var(--ink)]">活动标题 / 说明</label>
                <input
                  type="text"
                  required
                  placeholder="例如：社群专属满15减5元福利"
                  value={campaignForm.title}
                  onChange={(e) => setCampaignForm({ ...campaignForm, title: e.target.value })}
                  className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold mb-1 text-[color:var(--ink)]">
                  活动所属店铺 (必选，券跟着店铺走)
                </label>
                <select
                  required
                  value={campaignSelectedShopId}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCampaignSelectedShopId(val);
                    if (val === "custom") {
                      setCampaignForm({
                        ...campaignForm,
                        shop_id: null,
                        shop_name: "",
                        shop_url: "",
                      });
                    } else {
                      const s = platformShops.find((shop) => shop.id.toString() === val);
                      if (s) {
                        setCampaignForm({
                          ...campaignForm,
                          shop_id: s.id,
                          shop_name: s.name,
                          shop_url: s.source_url,
                        });
                      }
                    }
                  }}
                  className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2 text-xs focus:outline-none"
                >
                  <option value="">-- 请选择活动所属店铺 --</option>
                  {platformShops.map((s) => (
                    <option key={s.id} value={s.id.toString()}>
                      {s.name} ({s.token})
                    </option>
                  ))}
                  <option value="custom">✏️ 手动输入其他店铺...</option>
                </select>
                {campaignSelectedShopId === "custom" && (
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <input
                      type="text"
                      placeholder="店铺名称，如 彩头AI"
                      value={campaignForm.shop_name || ""}
                      onChange={(e) => setCampaignForm({ ...campaignForm, shop_name: e.target.value })}
                      className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-2.5 py-1.5 text-xs focus:outline-none"
                    />
                    <input
                      type="url"
                      placeholder="店铺链接，如 https://wzyp.cn/shop/..."
                      value={campaignForm.shop_url || ""}
                      onChange={(e) => setCampaignForm({ ...campaignForm, shop_url: e.target.value })}
                      className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-2.5 py-1.5 text-xs focus:outline-none"
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">绑定券批次 ID (选填)</label>
                  <input
                    type="number"
                    value={campaignForm.coupon_batch_id}
                    onChange={(e) => setCampaignForm({ ...campaignForm, coupon_batch_id: Number(e.target.value) })}
                    placeholder="0 表示通用券池"
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                  <p className="mt-1 text-[10px] text-black/40">如无特定批次请填 0 或留空，系统自动从通用券池发放</p>
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">单人限领 (张)</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={campaignForm.max_per_user}
                    onChange={(e) => setCampaignForm({ ...campaignForm, max_per_user: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">发放总配额 (张)</label>
                  <input
                    type="number"
                    min="1"
                    value={campaignForm.total_quota}
                    onChange={(e) => setCampaignForm({ ...campaignForm, total_quota: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-[color:var(--ink)]">有效天数</label>
                  <input
                    type="number"
                    min="1"
                    value={campaignForm.expires_days}
                    onChange={(e) => setCampaignForm({ ...campaignForm, expires_days: Number(e.target.value) })}
                    className="w-full rounded-lg border hairline border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-1.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[color:var(--line)]">
                <button
                  type="button"
                  onClick={() => setIsCampaignModalOpen(false)}
                  className="button-secondary tactile px-4 py-2 text-xs rounded-lg"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={creatingCampaign}
                  className="tactile inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--ink)] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:opacity-90 disabled:opacity-50"
                >
                  {creatingCampaign ? <ArrowClockwise size={13} className="animate-spin" /> : <Check size={13} weight="bold" />}
                  <span>{creatingCampaign ? "创建中..." : "确认创建"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
