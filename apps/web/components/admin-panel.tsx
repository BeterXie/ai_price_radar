"use client";
 
import { useEffect, useRef, useState } from "react";
import {
  ArrowClockwise,
  Article,
  Broadcast,
  ChatCircleDots,
  Check,
  Eye,
  EyeSlash,
  Gear,
  Gift,
  Globe,
  Key,
  MagnifyingGlass,
  Robot,
  Storefront,
  Tag,
  UsersThree,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { money, stockLabel } from "@/lib/format";
import { SourceDiscoveryPanel } from "@/components/source-discovery-panel";
import { SkillsAdminPanel } from "@/components/skills-admin-panel";
import { CouponsAdminPanel } from "@/components/coupons-admin-panel";
import { UsersAdminPanel } from "@/components/users-admin-panel";
import { BRAND_TABS, type BrandName, PRODUCT_TABS, ALL_PRODUCTS } from "@/lib/catalog";


const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
export type AdminTab = "settings" | "users" | "coupons" | "intakes" | "skills" | "discovery" | "reports" | "offers";
type CategoryMode = "all" | "restricted" | "unclassified" | BrandName;
type StatusFilter = "all" | "active" | "pending";
type StockFilter = "all" | "in_stock" | "out_of_stock";
type ScopeFilter = "current" | "all";
type OfferSort = "frontend" | "updated_desc" | "price_asc" | "price_desc";
type ReportFilter = "open" | "resolved" | "rejected" | "all";

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
  total_users?: number;
  last_scan_at: string | null;
  product_counts?: Record<string, number>;
  brand_counts?: Record<string, number>;
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
  stock_count?: number | null;
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
  const [activeTab, setActiveTab] = useState<AdminTab>("settings");
  const [key, setKey] = useState("");
  // The key accepted by the API. Child panels mount on this value, so typing a
  // partial key no longer fires 401 requests, and verifying a new key remounts
  // (and therefore reloads) the user/coupon panels.
  const [verifiedKey, setVerifiedKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [offers, setOffers] = useState<AdminOffer[]>([]);
  const [offerTotal, setOfferTotal] = useState<number>(0);
  const [offerSort, setOfferSort] = useState<OfferSort>("frontend");
  const [loadingMoreOffers, setLoadingMoreOffers] = useState<boolean>(false);
  const [selectedCategory, setSelectedCategory] = useState<CategoryMode>("all");
  const [selectedProductSlug, setSelectedProductSlug] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [stockFilter, setStockFilter] = useState<StockFilter>("all");
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("current");
  const [offerSearch, setOfferSearch] = useState("");
  const [reclassifyingOfferId, setReclassifyingOfferId] = useState<number | null>(null);
  const [actionToast, setActionToast] = useState<string>("");
  const [reports, setReports] = useState<Report[]>([]);
  const [reportFilter, setReportFilter] = useState<ReportFilter>("open");
  const [loadingReports, setLoadingReports] = useState(false);
  const [intakes, setIntakes] = useState<SourceIntake[]>([]);
  const [targetIntakeId, setTargetIntakeId] = useState<number | null>(null);
  const [reportDrafts, setReportDrafts] = useState<Record<number, { public_summary: string; merchant_response: string }>>({});
  const [intakeReasons, setIntakeReasons] = useState<Record<number, string>>({});
  const [advertiseEnabled, setAdvertiseEnabled] = useState<boolean>(false);
  const [updatingAdvertise, setUpdatingAdvertise] = useState<boolean>(false);
  const [botEnabled, setBotEnabled] = useState<boolean>(true);
  const [updatingBot, setUpdatingBot] = useState<boolean>(false);
  const [siteNotice, setSiteNotice] = useState({
    enabled: true,
    badge: "最新动态",
    title: "",
    content: "",
    link_text: "",
    link_url: "",
  });
  const [savingSiteNotice, setSavingSiteNotice] = useState<boolean>(false);
  const [communityNoticeForm, setCommunityNoticeForm] = useState({
    enabled: true,
    title: "加入 AI 比价交流群",
    desc: "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。",
    qq_group: "938741334",
    qq_url: "",
    btn_text: "一键加入 QQ 群",
  });
  const [savingCommunityNotice, setSavingCommunityNotice] = useState<boolean>(false);
  const [error, setError] = useState(previewState === "error" ? "管理数据暂时无法加载。输入密钥后可以重新连接。" : "");
  const headers = { "X-Admin-Key": key };
  // Child panels must use a verified credential, and remount when it changes.
  const verifiedHeaders = { "X-Admin-Key": verifiedKey };
  const hasScrolledToIntakeRef = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const intakeId = Number(params.get("intake"));
    if (Number.isInteger(intakeId) && intakeId > 0) {
      setTargetIntakeId(intakeId);
      setActiveTab("intakes");
    }
    const tabParam = params.get("tab") as AdminTab | null;
    const validTabs: AdminTab[] = ["settings", "users", "coupons", "intakes", "skills", "discovery", "reports", "offers"];
    if (tabParam && validTabs.includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, []);

  function switchTab(tab: AdminTab) {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", tab);
      window.history.replaceState(null, "", url.toString());
    }
  }

  useEffect(() => {
    if (hasScrolledToIntakeRef.current || targetIntakeId === null || !intakes.some((intake) => intake.id === targetIntakeId)) return;
    const element = document.getElementById(`intake-row-${targetIntakeId}`);
    if (element) {
      hasScrolledToIntakeRef.current = true;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [intakes, targetIntakeId]);

  async function preserveScroll<T>(action: () => Promise<T>): Promise<T> {
    const currentScrollY = typeof window !== "undefined" ? window.scrollY : 0;
    try {
      return await action();
    } finally {
      if (typeof window !== "undefined") {
        window.scrollTo({ top: currentScrollY, behavior: "instant" as ScrollBehavior });
        requestAnimationFrame(() => {
          window.scrollTo({ top: currentScrollY, behavior: "instant" as ScrollBehavior });
        });
      }
    }
  }

  async function loadOffers(
    category: CategoryMode = selectedCategory,
    productSlug: string = selectedProductSlug,
    status: StatusFilter = statusFilter,
    search: string = offerSearch,
    sort: OfferSort = offerSort,
    offset = 0,
    append = false,
    stock: StockFilter = stockFilter,
    scope: ScopeFilter = scopeFilter
  ) {
    const params = new URLSearchParams();
    params.set("limit", "100");
    params.set("offset", String(offset));
    params.set("sort", sort);
    params.set("scope", scope);
    if (stock !== "all") {
      params.set("stock_status", stock);
    }
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
      const data = await response.json();
      const totalHeader = response.headers.get("x-total-count");
      const total = totalHeader ? parseInt(totalHeader, 10) : data.length;
      setOfferTotal(total);
      if (append) {
        setOffers((prev) => [...prev, ...data]);
      } else {
        setOffers(data);
      }
    }
  }

  async function handleLoadMoreOffers() {
    setLoadingMoreOffers(true);
    try {
      await preserveScroll(async () => {
        await loadOffers(
          selectedCategory,
          selectedProductSlug,
          statusFilter,
          offerSearch,
          offerSort,
          offers.length,
          true,
          stockFilter,
          scopeFilter
        );
      });
    } finally {
      setLoadingMoreOffers(false);
    }
  }

  async function load() {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "100");
      params.set("sort", offerSort);
      params.set("scope", scopeFilter);
      if (stockFilter !== "all") params.set("stock_status", stockFilter);
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

      const [statsResponse, offersResponse, reportsResponse, intakesResponse, settingsResponse] = await Promise.all([
        fetch(`${API}/api/v1/admin/stats`, { headers }),
        fetch(`${API}/api/v1/admin/offers?${params.toString()}`, { headers }),
        fetch(`${API}/api/v1/admin/reports?status=${reportFilter}`, { headers }),
        fetch(`${API}/api/v1/admin/source-intakes`, { headers }),
        fetch(`${API}/api/v1/admin/settings`, { headers }).catch(() => null),
      ]);
      if (!statsResponse.ok || !offersResponse.ok || !reportsResponse.ok || !intakesResponse.ok) {
        setError("管理密钥无效，或 API 无法访问。密钥仍保留在当前页面，可以修改后重试。");
        setVerifiedKey("");
        return;
      }
      // Mark this key as verified so the child panels mount/reload with a
      // working credential instead of one typed character at a time.
      setVerifiedKey(key);
      setStats(await statsResponse.json());
      if (settingsResponse && settingsResponse.ok) {
        const settingsData = await settingsResponse.json();
        setAdvertiseEnabled(Boolean(settingsData.advertise_enabled));
        setBotEnabled(settingsData.bot_enabled ?? true);
        setSiteNotice({
          enabled: settingsData.site_notice_enabled ?? true,
          badge: settingsData.site_notice_badge || "最新动态",
          title: settingsData.site_notice_title || "",
          content: settingsData.site_notice_content || "",
          link_text: settingsData.site_notice_link_text || "",
          link_url: settingsData.site_notice_link_url || "",
        });
        setCommunityNoticeForm({
          enabled: settingsData.community_enabled ?? true,
          title: settingsData.community_title || "加入 AI 比价交流群",
          desc: settingsData.community_desc || "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。",
          qq_group: settingsData.community_qq_group || "938741334",
          qq_url: settingsData.community_qq_url || "",
          btn_text: settingsData.community_btn_text || "一键加入 QQ 群",
        });
      }
      const offersData = await offersResponse.json();
      const totalHeader = offersResponse.headers.get("x-total-count");
      setOfferTotal(totalHeader ? parseInt(totalHeader, 10) : offersData.length);
      setOffers(offersData);
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

  async function loadReports(status: ReportFilter = reportFilter) {
    if (!key) return;
    setLoadingReports(true);
    try {
      const response = await fetch(`${API}/api/v1/admin/reports?status=${status}`, { headers });
      if (response.ok) {
        const loadedReports = (await response.json()) as Report[];
        setReports(loadedReports);
        setReportDrafts((current) => ({
          ...current,
          ...Object.fromEntries(
            loadedReports.map((report) => [
              report.id,
              {
                public_summary: current[report.id]?.public_summary ?? (report.public_summary || ""),
                merchant_response: current[report.id]?.merchant_response ?? (report.merchant_response || ""),
              },
            ])
          ),
        }));
      }
    } finally {
      setLoadingReports(false);
    }
  }

  async function toggleAdvertise(targetState: boolean) {
    setUpdatingAdvertise(true);
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ advertise_enabled: targetState }),
      });
      if (response.ok) {
        const data = await response.json();
        setAdvertiseEnabled(Boolean(data.advertise_enabled));
        setActionToast(
          data.advertise_enabled
            ? "已开启商务合作与广告投放专区（前台已显示入口）"
            : "已关闭商务合作与广告投放专区（前台已隐藏入口）"
        );
      } else {
        setError("更新商务合作设置失败，请重试。");
      }
    } catch {
      setError("网络请求失败，未能更新商务合作设置。");
    } finally {
      setUpdatingAdvertise(false);
    }
  }

  async function toggleBot(targetState: boolean) {
    setUpdatingBot(true);
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ bot_enabled: targetState }),
      });
      if (response.ok) {
        const data = await response.json();
        setBotEnabled(Boolean(data.bot_enabled ?? true));
        setActionToast(
          data.bot_enabled
            ? "已开启 QQ 机器人服务（前台个人中心已显示绑定卡片）"
            : "已关闭 QQ 机器人服务（前台个人中心已完全隐藏）"
        );
      } else {
        setError("更新机器人开关失败，请重试。");
      }
    } catch {
      setError("网络请求失败，未能更新机器人设置。");
    } finally {
      setUpdatingBot(false);
    }
  }

  async function toggleSiteNoticeEnabled(targetState: boolean) {
    setSiteNotice((prev) => ({ ...prev, enabled: targetState }));
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ site_notice_enabled: targetState }),
      });
      if (response.ok) {
        const data = await response.json();
        setSiteNotice((prev) => ({ ...prev, enabled: Boolean(data.site_notice_enabled) }));
        setActionToast(
          data.site_notice_enabled
            ? "已启用页面顶部横条公告（前台已显示）"
            : "已停用页面顶部横条公告（前台已隐藏）"
        );
      } else {
        setError("更新顶部公告开关失败。");
      }
    } catch {
      setError("网络请求失败，未能更新顶部公告开关。");
    }
  }

  async function saveSiteNotice() {
    setSavingSiteNotice(true);
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          site_notice_enabled: siteNotice.enabled,
          site_notice_badge: siteNotice.badge.trim(),
          site_notice_title: siteNotice.title.trim(),
          site_notice_content: siteNotice.content.trim(),
          site_notice_link_text: siteNotice.link_text.trim(),
          site_notice_link_url: siteNotice.link_url.trim(),
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setSiteNotice({
          enabled: data.site_notice_enabled ?? true,
          badge: data.site_notice_badge || "最新动态",
          title: data.site_notice_title || "",
          content: data.site_notice_content || "",
          link_text: data.site_notice_link_text || "",
          link_url: data.site_notice_link_url || "",
        });
        setActionToast("页面顶部横条公告设置已保存并实时生效");
      } else {
        setError("保存页面顶部横条公告配置失败，请重试。");
      }
    } catch {
      setError("网络请求失败，未能保存页面顶部横条公告配置。");
    } finally {
      setSavingSiteNotice(false);
    }
  }

  async function toggleCommunityNoticeEnabled(targetState: boolean) {
    setCommunityNoticeForm((prev) => ({ ...prev, enabled: targetState }));
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ community_enabled: targetState }),
      });
      if (response.ok) {
        const data = await response.json();
        setCommunityNoticeForm((prev) => ({ ...prev, enabled: Boolean(data.community_enabled) }));
        setActionToast(
          data.community_enabled
            ? "已启用交流群引导弹窗（前台已开启）"
            : "已停用交流群引导弹窗（前台已隐藏）"
        );
      } else {
        setError("更新交流群引导弹窗开关失败。");
      }
    } catch {
      setError("网络请求失败，未能更新交流群引导弹窗开关。");
    }
  }

  async function saveCommunityNotice() {
    setSavingCommunityNotice(true);
    setActionToast("");
    try {
      const response = await fetch(`${API}/api/v1/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          community_enabled: communityNoticeForm.enabled,
          community_title: communityNoticeForm.title.trim(),
          community_desc: communityNoticeForm.desc.trim(),
          community_qq_group: communityNoticeForm.qq_group.trim(),
          community_qq_url: communityNoticeForm.qq_url.trim(),
          community_btn_text: communityNoticeForm.btn_text.trim(),
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setCommunityNoticeForm({
          enabled: data.community_enabled ?? true,
          title: data.community_title || "加入 AI 比价交流群",
          desc: data.community_desc || "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。",
          qq_group: data.community_qq_group || "938741334",
          qq_url: data.community_qq_url || "",
          btn_text: data.community_btn_text || "一键加入 QQ 群",
        });
        setActionToast("交流群引导弹窗配置已保存并实时生效");
      } else {
        setError("保存交流群引导弹窗配置失败，请重试。");
      }
    } catch {
      setError("网络请求失败，未能保存交流群引导弹窗配置。");
    } finally {
      setSavingCommunityNotice(false);
    }
  }

  async function patchOffer(offerId: number, body: Record<string, unknown>) {
    // 1. Optimistic in-place update so DOM doesn't collapse or lose focus
    setOffers((prev) =>
      prev.map((o) => {
        if (o.id !== offerId) return o;
        const updated = { ...o, ...body };
        if ("product_slug" in body) {
          const p = ALL_PRODUCTS.find((item) => item.slug === body.product_slug);
          updated.product_slug = (body.product_slug as string) || null;
          updated.product_name = p?.label || (body.product_slug as string) || null;
          updated.brand = p?.brand || null;
        }
        return updated;
      })
    );

    // 2. Perform network request while preserving scroll position
    await preserveScroll(async () => {
      const response = await fetch(`${API}/api/v1/admin/offers/${offerId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        const statsRes = await fetch(`${API}/api/v1/admin/stats`, { headers });
        if (statsRes.ok) setStats(await statsRes.json());
      }
    });
  }

  async function reclassifySingleOffer(offerId: number) {
    setReclassifyingOfferId(offerId);
    setActionToast("");
    await preserveScroll(async () => {
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
          const p = ALL_PRODUCTS.find((item) => item.slug === data.product_slug);
          setOffers((prev) =>
            prev.map((o) =>
              o.id === offerId
                ? {
                    ...o,
                    product_slug: data.product_slug || null,
                    product_name: p?.label || data.product_slug || null,
                    brand: p?.brand || null,
                  }
                : o
            )
          );
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
    });
  }

  async function reclassify() {
    await preserveScroll(async () => {
      const response = await fetch(`${API}/api/v1/admin/reclassify`, {
        method: "POST",
        headers,
      });
      if (response.ok) {
        const data = await response.json();
        setActionToast(`全量重新分类完成：变更 ${data.changed} 条，未分类 ${data.unclassified} 条`);
        await load();
      }
    });
  }

  async function resolveReport(reportId: number, status: "resolved" | "rejected") {
    const draft = reportDrafts[reportId] || { public_summary: "", merchant_response: "" };
    if (status === "resolved" && !draft.public_summary.trim()) {
      setError("发布已处理记录前，请填写不含联系方式和私密内容的公开摘要。");
      return;
    }
    await preserveScroll(async () => {
      const response = await fetch(`${API}/api/v1/admin/reports/${reportId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ status, public_summary: draft.public_summary.trim(), merchant_response: draft.merchant_response.trim() }),
      });
      if (response.ok) {
        setActionToast(status === "resolved" ? `反馈 #${reportId} 已标记处理并发布公开摘要` : `反馈 #${reportId} 已驳回`);
        await load();
        await loadReports(reportFilter);
      } else {
        const data = await response.json().catch(() => null);
        setError(data?.detail || "反馈状态更新失败，请重试。");
      }
    });
  }

  async function updateIntake(intakeId: number, action: "approve" | "reject" | "retry" | "redetect") {
    const body = action === "reject" ? { reason: (intakeReasons[intakeId] || "").trim() } : undefined;
    if (action === "reject" && !body?.reason) {
      setError("驳回收录申请前，请填写原因。");
      return;
    }
    await preserveScroll(async () => {
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
    });
  }

  async function updateIntakePlatform(intakeId: number, platform: string) {
    await preserveScroll(async () => {
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
    });
  }

  async function retryFailedIntakeNotifications(intakeId: number) {
    await preserveScroll(async () => {
      const response = await fetch(`${API}/api/v1/admin/source-intakes/${intakeId}/notifications/retry`, {
        method: "POST",
        headers,
      });
      if (response.ok) await load();
      else setError("失败邮件重发排队失败，请刷新后重试。");
    });
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
      {actionToast && (
        <div role="status" className="flex items-center justify-between rounded-[9px] border border-[color:var(--success)]/25 bg-[color:var(--success-soft)] p-4 text-sm font-medium text-[color:var(--success)]">
          <span>{actionToast}</span>
          <button type="button" onClick={() => setActionToast("")} className="ml-2 text-xs underline hover:opacity-80">关闭</button>
        </div>
      )}
      {!stats && !error && <section className="surface-subtle p-5" role="status"><p className="section-kicker">尚未连接</p><p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">输入管理密钥后加载当前统计、收录申请、纠错队列和最近报价。</p></section>}

      {stats && (
        <div className="sticky top-0 z-20 -mx-2 bg-[color:var(--paper)]/95 px-2 py-3 backdrop-blur-md border-b border-[color:var(--line)]">
          <nav className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none" aria-label="后台功能模块导航">
            {[
              { id: "settings" as const, label: "运营与配置", icon: Gear, count: 0 },
              { id: "users" as const, label: "用户管理", icon: UsersThree, count: stats.total_users || 0 },
              { id: "coupons" as const, label: "优惠券与营销", icon: Gift, count: 0 },
              { id: "intakes" as const, label: "店铺审核", icon: Storefront, count: stats.pending_source_intakes || 0 },
              { id: "skills" as const, label: "社区玩法与文章", icon: Article, count: 0 },
              { id: "discovery" as const, label: "公网来源发现", icon: Globe, count: 0 },
              { id: "reports" as const, label: "纠错与反馈", icon: WarningCircle, count: stats.open_corrections || 0 },
              { id: "offers" as const, label: "报价与分类", icon: Tag, count: stats.unclassified_offers || 0 },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => switchTab(tab.id)}
                  aria-current={isActive ? "page" : undefined}
                  className={`tactile inline-flex shrink-0 items-center gap-2 rounded-[10px] px-3.5 py-2 text-xs font-semibold transition-all ${
                    isActive
                      ? "bg-[color:var(--ink)] text-white shadow-sm"
                      : "border border-[color:var(--line-strong)]/60 bg-[color:var(--panel)] text-[color:var(--muted)] hover:border-[color:var(--ink)] hover:text-[color:var(--ink)]"
                  }`}
                >
                  <Icon size={16} weight={isActive ? "bold" : "regular"} />
                  <span>{tab.label}</span>
                  {tab.count > 0 && (
                    <span
                      className={`mono rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                        isActive
                          ? "bg-white/20 text-white"
                          : "bg-amber-100 text-amber-900 border border-amber-300"
                      }`}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      )}

      {/* Tab 1: 运营与配置 */}
      {stats && (
        <div style={{ display: activeTab === "settings" ? "block" : "none" }} className="space-y-8">
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

          {/* 商务合作 / 广告投放专区 */}
          <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4">
              <h2 className="text-base font-semibold">商务合作 / 广告投放专区</h2>
              <p className="mt-0.5 text-xs text-black/55">
                控制前台公开展示模块与业务开关。修改后实时生效，前台刷新页面即可看到变更。
              </p>
            </div>
            <div className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4">
                <div className="max-w-3xl">
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-sm font-semibold text-[color:var(--ink)]">商务合作入口与落地页</h3>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${advertiseEnabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)]"}`}>
                      {advertiseEnabled ? "已开启" : "已关闭"}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-5 text-[color:var(--muted)]">
                    开启后，将在全站页脚（Site Footer）、移动端抽屉导航、商户收录申请页（/shops/submit）及关于页展示「商务合作 / 广告投放」入口与联系邮箱（info@ai.pricememo.cn），且 /advertise 落地页对外公开可访问。关闭后，前台所有入口隐藏，直接访问 /advertise 返回 404。
                  </p>
                </div>
                <div className="shrink-0">
                  <button
                    type="button"
                    disabled={updatingAdvertise}
                    onClick={() => toggleAdvertise(!advertiseEnabled)}
                    className={`tactile inline-flex min-h-10 items-center justify-center rounded-[10px] px-5 text-xs font-semibold transition-all ${advertiseEnabled ? "border border-[color:var(--danger)] text-[color:var(--danger)] hover:bg-[color:var(--danger-soft)]" : "bg-[color:var(--ink)] text-white hover:opacity-90"} disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {updatingAdvertise ? "正在保存..." : advertiseEnabled ? "关闭商务合作专区" : "开启商务合作专区"}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* 机器人功能与变动推送开关 */}
          <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Robot size={18} weight="bold" className="text-blue-500" />
                QQ 机器人与价格变动通知开关
              </h2>
              <p className="mt-0.5 text-xs text-black/55">
                控制全站机器人（QQ Bot 等）推送服务及前台个人中心的通知绑定模块。修改后实时生效。
              </p>
            </div>
            <div className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-[14px] border border-[color:var(--line)] bg-[color:var(--surface)] p-4">
                <div className="max-w-3xl">
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-sm font-semibold text-[color:var(--ink)]">机器人服务与前台展示</h3>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${botEnabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)]"}`}>
                      {botEnabled ? "已开启" : "已关闭"}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-5 text-[color:var(--muted)]">
                    开启后，已登录用户可在个人中心（/account）通过手机 QQ 扫码或一键绑定机器人，接收降价/涨价私聊通知并使用 plus、pro、行情等交互指令。关闭后，前台个人中心将完全隐藏机器人绑定卡片，系统停止对外推送变动通知，且接口拒绝非管理员的绑定请求。
                  </p>
                </div>
                <div className="shrink-0">
                  <button
                    type="button"
                    disabled={updatingBot}
                    onClick={() => toggleBot(!botEnabled)}
                    className={`tactile inline-flex min-h-10 items-center justify-center rounded-[10px] px-5 text-xs font-semibold transition-all ${botEnabled ? "border border-[color:var(--danger)] text-[color:var(--danger)] hover:bg-[color:var(--danger-soft)]" : "bg-[color:var(--ink)] text-white hover:opacity-90"} disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {updatingBot ? "正在保存..." : botEnabled ? "关闭机器人功能" : "开启机器人功能"}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* 页面顶部横条公告 (Site Notice) */}
          <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 gap-2">
              <div>
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <Broadcast size={18} weight="bold" className="text-amber-500" />
                  页面顶部横条公告（Site Notice）
                </h2>
                <p className="mt-0.5 text-xs text-black/55">
                  全站页面顶部展示的通知横条，支持自定义徽标、标题、正文及跳转链接，前台支持点击叉号在本地会话关闭。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${siteNotice.enabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)] border hairline"}`}>
                  {siteNotice.enabled ? "已开启显示" : "已停用隐藏"}
                </span>
                <button
                  type="button"
                  onClick={() => toggleSiteNoticeEnabled(!siteNotice.enabled)}
                  className={`tactile inline-flex h-8 items-center justify-center rounded-[8px] px-3 text-xs font-medium border ${siteNotice.enabled ? "border-[color:var(--line-strong)] bg-[color:var(--panel)] hover:bg-[color:var(--subtle)] text-[color:var(--ink)]" : "bg-[color:var(--ink)] text-white"}`}
                >
                  {siteNotice.enabled ? "快速关闭" : "快速开启"}
                </button>
              </div>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    徽标标签（Badge）
                  </label>
                  <input
                    type="text"
                    value={siteNotice.badge}
                    onChange={(e) => setSiteNotice((prev) => ({ ...prev, badge: e.target.value }))}
                    placeholder="例如：最新动态、特别提示"
                    className="field text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    公告主标题（Title，选填）
                  </label>
                  <input
                    type="text"
                    value={siteNotice.title}
                    onChange={(e) => setSiteNotice((prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="例如：全量快照上线"
                    className="field text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-black/70 mb-1">
                  公告详细说明（Content）
                </label>
                <textarea
                  value={siteNotice.content}
                  onChange={(e) => setSiteNotice((prev) => ({ ...prev, content: e.target.value }))}
                  rows={2}
                  placeholder="例如：AI 比价雷达已升级至全量快照驱动，商品切换 0 延迟无白屏。"
                  className="w-full rounded-[8px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-3 text-sm text-[color:var(--ink)]"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    按钮文案（选填）
                  </label>
                  <input
                    type="text"
                    value={siteNotice.link_text}
                    onChange={(e) => setSiteNotice((prev) => ({ ...prev, link_text: e.target.value }))}
                    placeholder="例如：查看详情"
                    className="field text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    目标跳转链接（选填）
                  </label>
                  <input
                    type="text"
                    value={siteNotice.link_url}
                    onChange={(e) => setSiteNotice((prev) => ({ ...prev, link_url: e.target.value }))}
                    placeholder="例如：/articles/dujiao-vs-ldxp 或 https://..."
                    className="field text-sm"
                  />
                </div>
              </div>

              {/* 实时预览 */}
              <div className="rounded-[10px] border border-dashed border-[color:var(--line-strong)] p-3.5 bg-[color:var(--subtle)]/40">
                <p className="text-[11px] font-semibold text-[color:var(--muted)] mb-2 uppercase tracking-wider">
                  顶部横条公告实时预览效果
                </p>
                {siteNotice.enabled ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-[8px] border border-[color:var(--line)] bg-[color:var(--panel)] px-4 py-2.5 shadow-sm text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-[color:var(--ink)] px-2 py-0.5 text-[11px] font-bold text-white">
                        {siteNotice.badge || "最新动态"}
                      </span>
                      {siteNotice.title && (
                        <strong className="font-semibold text-[color:var(--ink)]">
                          {siteNotice.title}
                        </strong>
                      )}
                      <span className="text-[color:var(--muted)]">
                        {siteNotice.content || "（暂无公告正文内容）"}
                      </span>
                    </div>
                    {siteNotice.link_text && (
                      <span className="inline-flex items-center gap-1 font-semibold text-[color:var(--info)] underline">
                        {siteNotice.link_text}
                      </span>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-[color:var(--muted)] italic">
                    当前处于“已停用”状态，前台页面顶部不会渲染此横条。
                  </p>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  disabled={savingSiteNotice}
                  onClick={saveSiteNotice}
                  className="button-primary tactile disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingSiteNotice ? (
                    <>
                      <ArrowClockwise size={16} className="animate-spin" />
                      <span>保存中...</span>
                    </>
                  ) : (
                    <>
                      <Check size={16} />
                      <span>保存公告配置</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </section>

          {/* AI比价交流群引导配置 (Community Notice) */}
          <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 gap-2">
              <div>
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <UsersThree size={18} weight="bold" className="text-amber-500" />
                  加入 AI 比价交流群引导配置（Community Notice）
                </h2>
                <p className="mt-0.5 text-xs text-black/55">
                  全站右下角浮动弹窗展示的入群引导，可配置开关、提示标题、详细文案、QQ群号、加群链接及按钮文案。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${communityNoticeForm.enabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)] border hairline"}`}>
                  {communityNoticeForm.enabled ? "已开启显示" : "已停用隐藏"}
                </span>
                <button
                  type="button"
                  onClick={() => toggleCommunityNoticeEnabled(!communityNoticeForm.enabled)}
                  className={`tactile inline-flex h-8 items-center justify-center rounded-[8px] px-3 text-xs font-medium border ${communityNoticeForm.enabled ? "border-[color:var(--line-strong)] bg-[color:var(--panel)] hover:bg-[color:var(--subtle)] text-[color:var(--ink)]" : "bg-[color:var(--ink)] text-white"}`}
                >
                  {communityNoticeForm.enabled ? "快速关闭" : "快速开启"}
                </button>
              </div>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    弹窗主标题（Title）
                  </label>
                  <input
                    type="text"
                    value={communityNoticeForm.title}
                    onChange={(e) => setCommunityNoticeForm((prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="例如：加入 AI 比价交流群"
                    className="field text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    QQ交流群号（QQ Group）
                  </label>
                  <input
                    type="text"
                    value={communityNoticeForm.qq_group}
                    onChange={(e) => setCommunityNoticeForm((prev) => ({ ...prev, qq_group: e.target.value }))}
                    placeholder="例如：938741334"
                    className="field text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-black/70 mb-1">
                  详细说明文案（Description）
                </label>
                <textarea
                  value={communityNoticeForm.desc}
                  onChange={(e) => setCommunityNoticeForm((prev) => ({ ...prev, desc: e.target.value }))}
                  rows={2}
                  placeholder="第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态..."
                  className="w-full rounded-[8px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-3 text-sm text-[color:var(--ink)]"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    一键加群链接（QQ Group URL，选填）
                  </label>
                  <input
                    type="text"
                    value={communityNoticeForm.qq_url}
                    onChange={(e) => setCommunityNoticeForm((prev) => ({ ...prev, qq_url: e.target.value }))}
                    placeholder="例如：https://qm.qq.com/cgi-bin/qm/qr?k=..."
                    className="field text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-black/70 mb-1">
                    加群按钮文案（Button Text）
                  </label>
                  <input
                    type="text"
                    value={communityNoticeForm.btn_text}
                    onChange={(e) => setCommunityNoticeForm((prev) => ({ ...prev, btn_text: e.target.value }))}
                    placeholder="例如：一键加入 QQ 群"
                    className="field text-sm"
                  />
                </div>
              </div>

              {/* 实时预览 */}
              <div className="rounded-[10px] border border-dashed border-[color:var(--line-strong)] p-4 bg-[color:var(--subtle)]/40 max-w-md">
                <p className="text-[11px] font-semibold text-[color:var(--muted)] mb-2 uppercase tracking-wider">
                  弹窗效果实时预览
                </p>
                {communityNoticeForm.enabled ? (
                  <div className="rounded-[14px] border border-[color:var(--line)] bg-[color:var(--panel)] p-4 shadow-sm">
                    <div className="flex items-start gap-3">
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-[8px] bg-[color:var(--ink)] text-amber-400">
                        <UsersThree size={22} weight="bold" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-[color:var(--ink)]">
                          {communityNoticeForm.title || "加入 AI 比价交流群"}
                        </h3>
                        <p className="mt-1 text-xs leading-5 text-black/60">
                          {communityNoticeForm.desc || "第一时间获取各大卡网最新特价、库存补货、封号避坑与 API 渠道动态。"} QQ群号：{communityNoticeForm.qq_group || "938741334"}
                        </p>
                        <div className="mt-3 flex items-center gap-2">
                          <span className="inline-flex items-center justify-center rounded-[8px] bg-[color:var(--ink)] px-3 py-1.5 text-xs font-medium !text-white shadow-sm">
                            {communityNoticeForm.btn_text || "一键加入 QQ 群"}
                          </span>
                          <span className="rounded-[8px] border hairline px-3 py-1.5 text-xs text-[color:var(--muted)]">
                            稍后再说
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-[color:var(--muted)] italic">
                    当前入群引导处于“已停用”状态，前台不会弹出此提示。
                  </p>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  disabled={savingCommunityNotice}
                  onClick={saveCommunityNotice}
                  className="button-primary tactile disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingCommunityNotice ? (
                    <>
                      <ArrowClockwise size={16} className="animate-spin" />
                      <span>保存中...</span>
                    </>
                  ) : (
                    <>
                      <Check size={16} />
                      <span>保存群引导配置</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {/* Tab 2: 店铺审核 */}
      {stats && (
        <div style={{ display: activeTab === "intakes" ? "block" : "none" }}>
          {intakes.length > 0 ? (
            <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
              <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 font-semibold flex items-center justify-between">
                <span>店铺收录申请</span>
                <span className="text-xs text-[color:var(--muted)]">共 {intakes.length} 条申请</span>
              </div>
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
                      <p className="mt-2 text-xs text-black/50">联系邮箱：{intake.contact_email ? intake.contact_email : <span className="text-black/40">未填写（公网爬虫发现）</span>} · 商品数：{intake.product_count} · 重试次数：{intake.attempt_count}</p>
                      {intake.note && <p className="mt-2 whitespace-pre-line text-sm leading-6 text-black/65">申请说明：{intake.note}</p>}
                      {intake.source_type === "other" && intake.status === "pending_review" && <p className="mt-2 text-sm leading-6 text-black/65">提示：如该店铺为链动小铺、独角数卡等支持的平台，可在上方切换类型或点击“重新检测”；点击批准将自动按检测平台接入。</p>}
                      {["merchant_json", "woocommerce", "16688", "schema_org"].includes(intake.source_type) && intake.status === "approved" && <p className="mt-2 text-sm leading-6 text-black/65">等待目录发布流程安全拉取并分类商品；成功进入完整快照后才会公开。</p>}
                      {intake.failure_reason && <p className="mt-2 rounded-[10px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm leading-6 text-[color:var(--danger)]">失败原因：{intake.failure_reason}</p>}
                      {!intake.contact_email ? (
                        <p className="mt-3 text-xs text-black/40">无联系邮箱（系统爬虫自动发现，不发送邮件通知）</p>
                      ) : Object.keys(intake.email_status).length > 0 ? (
                        <p className="mt-3 text-xs text-black/50">邮件状态：{Object.entries(intake.email_status).map(([event, mailStatus]) => `${event} ${emailStatusLabel(mailStatus)}`).join(" · ")}</p>
                      ) : (
                        <p className="mt-3 text-xs text-black/40">暂无邮件记录</p>
                      )}
                      {intake.status === "pending_review" && <label className="mt-4 block text-xs font-medium text-black/55">驳回原因<input value={intakeReasons[intake.id] || ""} onChange={(event) => setIntakeReasons((current) => ({ ...current, [intake.id]: event.target.value }))} maxLength={500} placeholder="仅在驳回时必填" className="field mt-1.5 text-sm" /></label>}
                    </div>
                    <div className="flex flex-wrap gap-2 xl:justify-end">
                      {intake.status === "pending_review" && (
                        <>
                          <button type="button" onClick={() => updateIntake(intake.id, "approve")} className="button-primary tactile">
                            <Check size={16} />
                            {intake.source_type === "ldxp" ? "批准并验证" : intake.source_type === "other" ? "批准接入" : "批准并加入发布队列"}
                          </button>
                          <button type="button" onClick={() => updateIntake(intake.id, "redetect")} className="tactile rounded-[10px] border hairline px-3 py-2 text-sm" title="根据最新探测规则重新识别平台">
                            <ArrowClockwise size={16} className="mr-1 inline" />
                            重新检测
                          </button>
                          <button type="button" onClick={() => updateIntake(intake.id, "reject")} className="button-danger tactile">
                            <X size={16} />
                            驳回
                          </button>
                        </>
                      )}
                      {intake.source_type !== "other" && (intake.status === "no_products" || intake.status === "validation_failed") && <button type="button" onClick={() => updateIntake(intake.id, "retry")} className="tactile rounded-[10px] border hairline px-3 py-2 text-sm"><ArrowClockwise size={16} className="mr-1 inline" />重新验证</button>}
                      {Object.values(intake.email_status).some((mailStatus) => mailStatus === "failed") && <button type="button" onClick={() => retryFailedIntakeNotifications(intake.id)} className="tactile rounded-[10px] border border-[color:var(--danger)] px-3 py-2 text-sm text-[color:var(--danger)]"><ArrowClockwise size={16} className="mr-1 inline" />重发失败邮件</button>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <div className="empty-state">
              <Storefront size={40} className="mx-auto mb-2 text-[color:var(--muted)] opacity-60" />
              <p className="text-base font-semibold text-[color:var(--ink)]">暂无待处理的店铺收录申请</p>
              <p className="mt-1 text-xs text-[color:var(--muted)]">商户在 /shops/submit 提交的新店铺申请将展示在此处供管理员审核。</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: 用户管理 */}
      {verifiedKey && (
        <div style={{ display: activeTab === "users" ? "block" : "none" }}>
          <UsersAdminPanel key={verifiedKey} apiBase={API} headers={verifiedHeaders} />
        </div>
      )}

      {/* Tab: 优惠券与营销 */}
      {verifiedKey && (
        <div style={{ display: activeTab === "coupons" ? "block" : "none" }}>
          <CouponsAdminPanel key={verifiedKey} apiBase={API} headers={verifiedHeaders} />
        </div>
      )}

      {/* Tab 3: 社区玩法与文章 */}
      {verifiedKey && (
        <div style={{ display: activeTab === "skills" ? "block" : "none" }}>
          <SkillsAdminPanel key={verifiedKey} apiBase={API} headers={verifiedHeaders} />
        </div>
      )}

      {/* Tab 4: 公网来源发现 */}
      {verifiedKey && (
        <div style={{ display: activeTab === "discovery" ? "block" : "none" }}>
          <SourceDiscoveryPanel key={verifiedKey} apiBase={API} headers={verifiedHeaders} />
        </div>
      )}

      {/* Tab 5: 纠错与风险反馈 */}
      {stats && (
        <div style={{ display: activeTab === "reports" ? "block" : "none" }}>
          <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">纠错与风险反馈</h2>
                <p className="mt-0.5 text-xs text-black/55">前台用户提交的报错或购买风险汇总。支持调查、核验后填写公开结论或驳回。</p>
              </div>
              <button
                type="button"
                onClick={() => loadReports(reportFilter)}
                className="tactile text-xs border hairline px-2.5 py-1.5 rounded-[8px] bg-[color:var(--panel)] hover:bg-[color:var(--subtle)] flex items-center gap-1.5"
              >
                <ArrowClockwise size={14} className={loadingReports ? "animate-spin" : ""} />
                刷新
              </button>
            </div>

            {/* Sub-tab filter buttons */}
            <div className="flex flex-wrap items-center gap-2 border-b border-[color:var(--line)] bg-[color:var(--panel)] px-5 py-3">
              {[
                { id: "open" as const, label: "待处理", count: stats.open_corrections },
                { id: "resolved" as const, label: "已处理" },
                { id: "rejected" as const, label: "已驳回" },
                { id: "all" as const, label: "全部记录" },
              ].map((filterItem) => (
                <button
                  key={filterItem.id}
                  type="button"
                  onClick={() => {
                    setReportFilter(filterItem.id);
                    loadReports(filterItem.id);
                  }}
                  className={`tactile flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-xs font-medium transition-colors ${
                    reportFilter === filterItem.id
                      ? "bg-[color:var(--ink)] text-white"
                      : "bg-[color:var(--subtle)] text-[color:var(--ink)] hover:bg-[color:var(--line)]"
                  }`}
                >
                  <span>{filterItem.label}</span>
                  {typeof filterItem.count === "number" && filterItem.count > 0 && (
                    <span
                      className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                        reportFilter === filterItem.id ? "bg-white/20 text-white" : "bg-red-500 text-white"
                      }`}
                    >
                      {filterItem.count}
                    </span>
                  )}
                </button>
              ))}
              {loadingReports && <span className="text-xs text-[color:var(--muted)] ml-2">加载中...</span>}
            </div>

            {/* Content List */}
            {reports.length > 0 ? (
              <div className="divide-y divide-[color:var(--line)]">
                {reports.map((report) => (
                  <div key={report.id} className="grid gap-4 px-5 py-4 md:grid-cols-[1fr_auto] md:items-start">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-[6px] bg-[color:var(--subtle)] px-2 py-0.5 text-xs font-medium mono text-black/60">
                          #{report.id} · {REPORT_KIND_LABELS[report.kind] || report.kind}
                        </span>
                        {report.status === "open" && (
                          <span className="rounded-[6px] bg-amber-500/15 px-2 py-0.5 text-xs font-semibold text-amber-700">待处理</span>
                        )}
                        {report.status === "resolved" && (
                          <span className="rounded-[6px] bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-700">已处理</span>
                        )}
                        {report.status === "rejected" && (
                          <span className="rounded-[6px] bg-slate-500/15 px-2 py-0.5 text-xs font-semibold text-slate-600">已驳回</span>
                        )}
                        {report.offer_id ? (
                          <span className="text-xs mono text-[color:var(--muted)]">关联报价 #{report.offer_id}</span>
                        ) : null}
                        <span className="text-xs text-[color:var(--muted)] ml-auto">
                          提交于 {new Date(report.created_at).toLocaleString("zh-CN", { hour12: false })}
                        </span>
                      </div>

                      <div className="rounded-[8px] bg-[color:var(--subtle)] p-3 text-sm leading-6 text-[color:var(--ink)] whitespace-pre-line">
                        {report.message}
                      </div>

                      {report.contact ? (
                        <p className="text-xs text-black/55">用户联系方式：<span className="font-mono text-[color:var(--ink)]">{report.contact}</span></p>
                      ) : null}

                      {/* If resolved */}
                      {report.status === "resolved" && (
                        <div className="rounded-[8px] border hairline border-emerald-500/30 bg-emerald-50/50 p-3 text-xs space-y-1">
                          <p className="font-medium text-emerald-900">公开处理摘要：{report.public_summary || "（未填写公开摘要）"}</p>
                          {report.merchant_response ? (
                            <p className="text-emerald-800">商家公开回应：{report.merchant_response}</p>
                          ) : null}
                          {report.resolved_at ? (
                            <p className="text-[10px] text-emerald-700">处理时间：{new Date(report.resolved_at).toLocaleString("zh-CN", { hour12: false })}</p>
                          ) : null}
                        </div>
                      )}

                      {/* If rejected */}
                      {report.status === "rejected" && (
                        <div className="rounded-[8px] border hairline border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                          已驳回此反馈。{report.resolved_at ? `处理时间：${new Date(report.resolved_at).toLocaleString("zh-CN", { hour12: false })}` : ""}
                        </div>
                      )}

                      {/* If open, show editing inputs */}
                      {report.status === "open" && (
                        <div className="mt-3 grid gap-3">
                          <label className="text-xs font-medium text-black/55">
                            公开处理摘要 <span className="text-red-500">*</span>
                            <textarea
                              value={reportDrafts[report.id]?.public_summary || ""}
                              onChange={(event) =>
                                setReportDrafts((current) => ({
                                  ...current,
                                  [report.id]: {
                                    ...(current[report.id] || { merchant_response: "" }),
                                    public_summary: event.target.value,
                                  },
                                }))
                              }
                              maxLength={500}
                              rows={2}
                              placeholder="只写适合公开的事实结论，不要复制联系方式或私密内容。"
                              className="mt-1.5 w-full rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm text-[color:var(--ink)]"
                            />
                          </label>
                          <label className="text-xs font-medium text-black/55">
                            商家公开回应 <span className="font-normal text-[color:var(--muted)]">选填</span>
                            <textarea
                              value={reportDrafts[report.id]?.merchant_response || ""}
                              onChange={(event) =>
                                setReportDrafts((current) => ({
                                  ...current,
                                  [report.id]: {
                                    ...(current[report.id] || { public_summary: "" }),
                                    merchant_response: event.target.value,
                                  },
                                }))
                              }
                              maxLength={1000}
                              rows={2}
                              className="mt-1.5 w-full rounded-[10px] border hairline bg-[color:var(--panel)] px-3 py-2 text-sm text-[color:var(--ink)]"
                            />
                          </label>
                        </div>
                      )}
                    </div>

                    {report.status === "open" && (
                      <div className="flex gap-2 md:self-end">
                        <button
                          type="button"
                          onClick={() => resolveReport(report.id, "resolved")}
                          className="tactile flex items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-3 py-2 text-sm text-white"
                        >
                          <Check size={16} />已处理
                        </button>
                        <button
                          type="button"
                          onClick={() => resolveReport(report.id, "rejected")}
                          className="tactile flex items-center gap-2 rounded-[10px] border hairline px-3 py-2 text-sm"
                        >
                          <X size={16} />驳回
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state py-12">
                <WarningCircle size={40} className="mx-auto mb-2 text-[color:var(--muted)] opacity-60" />
                <p className="text-base font-semibold text-[color:var(--ink)]">
                  {reportFilter === "open"
                    ? "暂无待处理的纠错与风险反馈"
                    : reportFilter === "resolved"
                    ? "暂无已处理的纠错记录"
                    : reportFilter === "rejected"
                    ? "暂无已驳回的纠错记录"
                    : "暂无纠错与风险反馈记录"}
                </p>
                <p className="mt-1 text-xs text-[color:var(--muted)]">
                  {reportFilter === "open"
                    ? "当用户在前台提交新的报错或购买风险时，将汇总在此处等待处理。"
                    : "历史已处理或已驳回的记录会在此处归档留存。"}
                </p>
              </div>
            )}
          </section>
        </div>
      )}

      {/* Tab 6: 报价与分类 */}
      {stats && (
        <div style={{ display: activeTab === "offers" ? "block" : "none" }}>
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
                  loadOffers("all", "", statusFilter, offerSearch, offerSort);
                }}
                aria-current={selectedCategory === "all" ? "page" : undefined}
                className="filter-chip"
              >
                全部品牌
                {typeof stats?.public_offers === "number" && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 mono text-[10px] ml-1.5 ${
                      selectedCategory === "all"
                        ? "bg-white/20 text-white"
                        : "bg-black/5 text-black/60"
                    }`}
                  >
                    {stats.public_offers}
                  </span>
                )}
              </button>
              {BRAND_TABS.map((brand) => {
                const count = stats?.brand_counts?.[brand];
                return (
                  <button
                    key={brand}
                    type="button"
                    onClick={() => {
                      setSelectedCategory(brand);
                      setSelectedProductSlug("");
                      loadOffers(brand, "", statusFilter, offerSearch, offerSort);
                    }}
                    aria-current={selectedCategory === brand ? "page" : undefined}
                    className="filter-chip"
                  >
                    {brand}
                    {typeof count === "number" && (
                      <span
                        className={`rounded-full px-1.5 py-0.2 mono text-[10px] ml-1.5 ${
                          selectedCategory === brand
                            ? "bg-white/20 text-white"
                            : "bg-black/5 text-black/60"
                        }`}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
              <div className="mx-1 h-5 w-px bg-[color:var(--line-strong)] self-center hidden sm:block" />
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory("restricted");
                  setSelectedProductSlug("");
                  loadOffers("restricted", "", "all", offerSearch, offerSort);
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
                  loadOffers("unclassified", "", "all", offerSearch, offerSort);
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
                {(() => {
                  const totalCount = selectedCategory === "all" ? stats?.public_offers : stats?.brand_counts?.[selectedCategory];
                  return (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedProductSlug("");
                        loadOffers(selectedCategory, "", statusFilter, offerSearch, offerSort);
                      }}
                      aria-current={selectedProductSlug === "" ? "page" : undefined}
                      className="filter-chip"
                    >
                      {selectedCategory === "all" ? "全部商品" : `全部 ${selectedCategory}`}
                      {typeof totalCount === "number" && (
                        <span
                          className={`rounded-full px-1.5 py-0.2 mono text-[10px] ml-1.5 ${
                            selectedProductSlug === ""
                              ? "bg-white/20 text-white"
                              : "bg-black/5 text-black/60"
                          }`}
                        >
                          {totalCount}
                        </span>
                      )}
                    </button>
                  );
                })()}
                {(selectedCategory === "all" ? ALL_PRODUCTS : PRODUCT_TABS[selectedCategory as BrandName] || []).map((tab) => {
                  const pCount = stats?.product_counts?.[tab.slug];
                  return (
                    <button
                      key={tab.slug}
                      type="button"
                      onClick={() => {
                        setSelectedProductSlug(tab.slug);
                        loadOffers(selectedCategory, tab.slug, statusFilter, offerSearch, offerSort);
                      }}
                      aria-current={selectedProductSlug === tab.slug ? "page" : undefined}
                      className="filter-chip"
                    >
                      {selectedCategory === "all" && "brand" in tab && (
                        <span className="text-[10px] opacity-60 mr-1">{String(tab.brand)}</span>
                      )}
                      {tab.label}
                      {typeof pCount === "number" && (
                        <span
                          className={`rounded-full px-1.5 py-0.2 mono text-[10px] ml-1.5 ${
                            selectedProductSlug === tab.slug
                              ? "bg-white/20 text-white"
                              : "bg-black/5 text-black/60"
                          }`}
                        >
                          {pCount}
                        </span>
                      )}
                    </button>
                  );
                })}
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

          {/* Search & Status / Sort Sub-Filter */}
          <div className="grid gap-3 border-b border-[color:var(--line)] bg-[color:var(--panel)] p-4 sm:grid-cols-[1fr_auto]">
            <div className="relative">
              <input
                value={offerSearch}
                onChange={(e) => setOfferSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch, offerSort, 0, false, stockFilter, scopeFilter);
                  }
                }}
                placeholder="按标题、店铺名称、拦截原因或 #报价ID 搜索..."
                className="w-full rounded-[9px] border border-[color:var(--line-strong)] bg-transparent py-2 pl-9 pr-3 text-sm outline-none focus:border-[color:var(--focus)]"
              />
              <MagnifyingGlass size={16} className="absolute left-3 top-3 text-black/40" />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={scopeFilter}
                onChange={(e) => {
                  const nextScope = e.target.value as ScopeFilter;
                  setScopeFilter(nextScope);
                  loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch, offerSort, 0, false, stockFilter, nextScope);
                }}
                className="rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-sm text-black/75 outline-none font-medium"
                title="按快照数据范围筛选"
              >
                <option value="current">范围：当前在售快照 (默认)</option>
                <option value="all">范围：全部历史记录</option>
              </select>

              <select
                value={offerSort}
                onChange={(e) => {
                  const nextSort = e.target.value as OfferSort;
                  setOfferSort(nextSort);
                  loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch, nextSort, 0, false, stockFilter, scopeFilter);
                }}
                className="rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-sm text-black/75 outline-none"
                title="选择报价排序方式"
              >
                <option value="frontend">前台默认（在售优先·低价优先）</option>
                <option value="updated_desc">最新更新时间优先</option>
                <option value="price_asc">价格从低到高</option>
                <option value="price_desc">价格从高到低</option>
              </select>

              {selectedCategory !== "restricted" && selectedCategory !== "unclassified" && (
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    const nextStatus = e.target.value as StatusFilter;
                    setStatusFilter(nextStatus);
                    loadOffers(selectedCategory, selectedProductSlug, nextStatus, offerSearch, offerSort, 0, false, stockFilter, scopeFilter);
                  }}
                  className="rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-sm text-black/75 outline-none"
                >
                  <option value="all">全部公开状态</option>
                  <option value="active">仅看公开中</option>
                  <option value="pending">仅看未公开/待审</option>
                </select>
              )}

              <select
                value={stockFilter}
                onChange={(e) => {
                  const nextStock = e.target.value as StockFilter;
                  setStockFilter(nextStock);
                  loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch, offerSort, 0, false, nextStock, scopeFilter);
                }}
                className="rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-sm text-black/75 outline-none"
                title="按库存状态筛选"
              >
                <option value="all">全部库存状态</option>
                <option value="in_stock">仅看有货</option>
                <option value="out_of_stock">仅看缺货</option>
              </select>

              <button
                type="button"
                onClick={() => loadOffers(selectedCategory, selectedProductSlug, statusFilter, offerSearch, offerSort, 0, false, stockFilter, scopeFilter)}
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

          {/* Offer Summary & Sort Info Header */}
          <div className="flex flex-wrap items-center justify-between border-b border-[color:var(--line)] bg-[color:var(--subtle)]/40 px-5 py-2.5 text-xs text-black/60">
            <div>
              共 <strong className="text-[color:var(--ink)] mono">{offerTotal}</strong> 条报价
              {offers.length < offerTotal ? (
                <span>（已载入前 <span className="mono text-[color:var(--ink)]">{offers.length}</span> 条）</span>
              ) : (
                <span>（已载入全部）</span>
              )}
            </div>
            <div className="text-[11px] text-black/45">
              当前排序：
              {offerSort === "frontend" && "前台默认（在售优先 · 低价优先 · 最新采集）"}
              {offerSort === "updated_desc" && "按最新采集更新时间"}
              {offerSort === "price_asc" && "按价格从低到高"}
              {offerSort === "price_desc" && "按价格从高到低"}
            </div>
          </div>

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
                      {offer.stock_status === "in_stock" ? (
                        <span
                          className="status-pill status-success"
                          title={offer.stock_count !== null && offer.stock_count !== undefined ? `当前在售库存 ${offer.stock_count} 件` : "在售有货"}
                        >
                          {offer.stock_count !== null && offer.stock_count !== undefined
                            ? `库存 ${offer.stock_count} 件`
                            : "有货"}
                        </span>
                      ) : offer.stock_status === "out_of_stock" ? (
                        <span className="status-pill status-danger" title="当前无货缺货中">
                          缺货{offer.stock_count !== null && offer.stock_count !== undefined ? ` (0件)` : ""}
                        </span>
                      ) : offer.stock_status === "unavailable" ? (
                        <span className="status-pill status-danger" title="商品已下架或不可用">
                          不可用
                        </span>
                      ) : (
                        <span className="status-pill" title="库存状态未知">
                          {stockLabel(offer.stock_status)}
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
                    <span className="mono font-semibold">{money(offer.price, offer.currency)}</span>
                    <br />
                    <span
                      className={`text-xs ${
                        offer.stock_status === "in_stock"
                          ? "font-medium text-[color:var(--success)]"
                          : offer.stock_status === "out_of_stock"
                          ? "text-[color:var(--danger)]"
                          : "text-black/40"
                      }`}
                    >
                      {stockLabel(offer.stock_status)}
                      {offer.stock_count !== null && offer.stock_count !== undefined
                        ? ` · ${offer.stock_count}件`
                        : ""}
                    </span>
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

          {offers.length < offerTotal && (
            <div className="border-t border-[color:var(--line)] bg-[color:var(--subtle)]/30 p-4 text-center">
              <button
                type="button"
                disabled={loadingMoreOffers}
                onClick={handleLoadMoreOffers}
                className="button-secondary tactile inline-flex items-center gap-2 px-6 py-2 text-sm disabled:opacity-50"
              >
                {loadingMoreOffers ? (
                  <>
                    <ArrowClockwise size={15} className="animate-spin" />
                    正在载入更多报价...
                  </>
                ) : (
                  `加载更多报价（还剩 ${offerTotal - offers.length} 条未载入）`
                )}
              </button>
            </div>
          )}
        </section>
        </div>
      )}
    </div>
  );
}
