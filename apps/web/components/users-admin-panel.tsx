"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowClockwise,
  ArrowSquareOut,
  Bell,
  Check,
  CheckCircle,
  Clock,
  Copy,
  Cursor,
  EnvelopeSimple,
  Eye,
  EyeSlash,
  Gift,
  Globe,
  MagnifyingGlass,
  Megaphone,
  PaperPlaneTilt,
  Robot,
  Sparkle,
  Ticket,
  User,
  UsersThree,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import type {
  AdminBroadcastAudienceOut,
  AdminBroadcastItem,
  AdminUserActionLogItem,
  AdminUserDetailOut,
  AdminUserItem,
  AdminUserPageOut,
  AdminUserSessionItem,
  AdminUserStatsOut,
  ShopCoupon,
  UserBotBinding,
} from "@/lib/types";

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "0秒";
  if (seconds < 60) return `${seconds}秒`;
  const mins = Math.floor(seconds / 60);
  const remSecs = seconds % 60;
  if (mins < 60) {
    return remSecs > 0 ? `${mins}分${remSecs}秒` : `${mins}分钟`;
  }
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return remMins > 0 ? `${hours}小时${remMins}分` : `${hours}小时`;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "从未登录";
  const now = new Date();
  const dt = new Date(dateStr);
  const diffSecs = Math.floor((now.getTime() - dt.getTime()) / 1000);

  if (diffSecs < 10) return "刚刚";
  if (diffSecs < 60) return `${diffSecs}秒前`;
  const diffMins = Math.floor(diffSecs / 60);
  if (diffMins < 60) return `${diffMins}分钟前`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays <= 7) return `${diffDays}天前`;

  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return "-";
  const dt = new Date(dateStr);
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  const ss = String(dt.getSeconds()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}

export function UsersAdminPanel({
  apiBase,
  headers,
}: {
  apiBase: string;
  headers: Record<string, string>;
}) {
  // Stats
  const [stats, setStats] = useState<AdminUserStatsOut | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Users list
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  // The keyword actually applied to requests; updated only on submit/clear so a
  // pending debounce or a setPage(1) cannot resend a stale query.
  const [appliedQuery, setAppliedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("last_login");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // User detail drawer
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [userDetail, setUserDetail] = useState<AdminUserDetailOut | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<"sessions" | "coupons" | "logs" | "bot">("sessions");
  const [togglingStatusId, setTogglingStatusId] = useState<number | null>(null);
  // Monotonic request id so an out-of-order detail response cannot overwrite a
  // newer selection (e.g. open A, close, open B, A resolves late).
  const detailRequestSeqRef = useRef(0);
  const usersRequestSeqRef = useRef(0);

  // Broadcast Notification Modal
  const [showBroadcastModal, setShowBroadcastModal] = useState(false);
  const [broadcastAudience, setBroadcastAudience] = useState<AdminBroadcastAudienceOut | null>(null);
  const [loadingAudience, setLoadingAudience] = useState(false);
  const [broadcastTitle, setBroadcastTitle] = useState("");
  const [broadcastContent, setBroadcastContent] = useState("");
  const [broadcastEmail, setBroadcastEmail] = useState(true);
  const [broadcastBot, setBroadcastBot] = useState(true);
  const [sendingBroadcast, setSendingBroadcast] = useState(false);
  const [broadcastHistory, setBroadcastHistory] = useState<AdminBroadcastItem[]>([]);
  const [loadingBroadcastHistory, setLoadingBroadcastHistory] = useState(false);
  const [broadcastSubTab, setBroadcastSubTab] = useState<"send" | "history">("send");
  const broadcastOperationRef = useRef<{ fingerprint: string; key: string } | null>(null);

  async function openBroadcastModal() {
    setShowBroadcastModal(true);
    setBroadcastSubTab("send");
    void fetchBroadcastAudience();
    void fetchBroadcastHistory();
  }

  async function fetchBroadcastAudience() {
    setLoadingAudience(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/broadcasts/audience`, { headers });
      if (res.ok) {
        const data = await res.json();
        setBroadcastAudience(data);
      }
    } catch {
      // Ignore
    } finally {
      setLoadingAudience(false);
    }
  }

  async function fetchBroadcastHistory() {
    setLoadingBroadcastHistory(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/broadcasts?limit=20`, { headers });
      if (res.ok) {
        const data = await res.json();
        setBroadcastHistory(data);
      }
    } catch {
      // Ignore
    } finally {
      setLoadingBroadcastHistory(false);
    }
  }

  async function handleSendBroadcast(e: React.FormEvent) {
    e.preventDefault();
    if (!broadcastTitle.trim() || !broadcastContent.trim()) {
      showToast("请完整填写通知标题与正文内容");
      return;
    }
    const channels: string[] = [];
    if (broadcastEmail) channels.push("email");
    if (broadcastBot) channels.push("bot");
    if (channels.length === 0) {
      showToast("请至少选择一个发送渠道（邮件或机器人）");
      return;
    }

    setSendingBroadcast(true);
    try {
      const payload = {
        title: broadcastTitle.trim(),
        content: broadcastContent.trim(),
        channels,
      };
      const fingerprint = JSON.stringify(payload);
      if (broadcastOperationRef.current?.fingerprint !== fingerprint) {
        const randomPart = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        broadcastOperationRef.current = { fingerprint, key: `broadcast-${randomPart}` };
      }
      const res = await fetch(`${apiBase}/api/v1/admin/broadcasts`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          operation_key: broadcastOperationRef.current.key,
        }),
      });
      if (res.ok) {
        const created = await res.json();
        showToast(`已成功广播通知！触达 ${created.target_user_count} 位用户`);
        setBroadcastTitle("");
        setBroadcastContent("");
        broadcastOperationRef.current = null;
        void fetchBroadcastHistory();
        setBroadcastSubTab("history");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "推送通知失败，请检查网络或后端");
      }
    } catch (err: any) {
      showToast("请求发生异常: " + (err?.message || "网络错误"));
    } finally {
      setSendingBroadcast(false);
    }
  }

  useEffect(() => {
    void fetchStats();
  }, []);

  // Refetch is driven by the *committed* query (appliedQuery) rather than the
  // raw input value, so clearing search or re-submitting cannot fire a request
  // that still carries the previous keyword.
  useEffect(() => {
    void fetchUsers();
  }, [page, limit, statusFilter, sortBy, order, appliedQuery]);

  async function fetchStats() {
    setLoadingStats(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/users/stats`, { headers });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      // Ignore network errors on auto-refresh
    } finally {
      setLoadingStats(false);
    }
  }

  async function fetchUsers() {
    const requestSeq = ++usersRequestSeqRef.current;
    setLoadingUsers(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("limit", String(limit));
      params.set("status", statusFilter);
      params.set("sort_by", sortBy);
      params.set("order", order);
      if (appliedQuery.trim()) {
        params.set("q", appliedQuery.trim());
      }

      const res = await fetch(`${apiBase}/api/v1/admin/users?${params.toString()}`, { headers });
      if (requestSeq !== usersRequestSeqRef.current) return;
      if (res.ok) {
        const data: AdminUserPageOut = await res.json();
        if (requestSeq !== usersRequestSeqRef.current) return;
        setUsers(data.items);
        setTotal(data.total);
      } else {
        showToast(`获取用户列表失败 (${res.status})`);
      }
    } catch {
      if (requestSeq === usersRequestSeqRef.current) {
        showToast("获取用户列表失败，请检查网络或管理凭证");
      }
    } finally {
      if (requestSeq === usersRequestSeqRef.current) {
        setLoadingUsers(false);
      }
    }
  }

  async function openUserDetail(userId: number) {
    setSelectedUserId(userId);
    setLoadingDetail(true);
    setDetailTab("sessions");
    // Drop the previous user's detail immediately so a slow/out-of-order
    // response can never be shown against a different account.
    setUserDetail(null);
    const requestSeq = ++detailRequestSeqRef.current;
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/users/${userId}`, { headers });
      if (requestSeq !== detailRequestSeqRef.current) {
        // A newer selection superseded this request.
        return;
      }
      if (res.ok) {
        const data: AdminUserDetailOut = await res.json();
        if (requestSeq !== detailRequestSeqRef.current) return;
        setUserDetail(data);
      } else {
        showToast("获取用户详情失败");
      }
    } catch {
      if (requestSeq === detailRequestSeqRef.current) {
        showToast("网络请求异常");
      }
    } finally {
      if (requestSeq === detailRequestSeqRef.current) {
        setLoadingDetail(false);
      }
    }
  }

  function closeUserDetail() {
    // Invalidate any in-flight detail request when the panel closes.
    detailRequestSeqRef.current += 1;
    setSelectedUserId(null);
    setUserDetail(null);
    setLoadingDetail(false);
  }

  async function toggleUserStatus(userId: number, currentActive: boolean) {
    setTogglingStatusId(userId);
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/users/${userId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({ is_active: !currentActive }),
      });
      if (res.ok) {
        const newActive = !currentActive;
        // Update user in state list
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, is_active: newActive } : u))
        );
        if (userDetail && userDetail.user.id === userId) {
          setUserDetail({
            ...userDetail,
            user: { ...userDetail.user, is_active: newActive },
          });
        }
        showToast(newActive ? "账号已解除封禁，恢复正常访问" : "账号已被封禁/禁用");
      } else {
        showToast("切换账号状态失败");
      }
    } catch {
      showToast("网络请求失败");
    } finally {
      setTogglingStatusId(null);
    }
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    // Reset both at once: changing appliedQuery triggers the fetch effect, so
    // no manual fetchUsers() call is needed (and calling it here would fire
    // another request with the pre-update page value).
    setAppliedQuery(searchQuery);
  }

  function showToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  }

  function copyToClipboard(text: string, label: string) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    showToast(`已复制 ${label}: ${text}`);
    setTimeout(() => setCopiedText(null), 2000);
  }

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Toast notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-4 py-3 shadow-xl text-sm font-medium text-[color:var(--ink)]">
          <Sparkle size={16} className="text-violet-600 shrink-0" weight="fill" />
          <span>{toastMessage}</span>
          <button
            type="button"
            onClick={() => setToastMessage("")}
            className="ml-2 text-xs text-[color:var(--muted)] hover:text-[color:var(--ink)]"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Header bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-lg font-bold tracking-tight text-[color:var(--ink)]">用户管理与活跃度大盘</h2>
            <span className="inline-flex items-center rounded-full bg-violet-500/10 px-2.5 py-0.5 text-xs font-semibold text-violet-700">
              实时追踪
            </span>
          </div>
          <p className="mt-1 text-xs text-[color:var(--muted)]">
            查看全站注册用户体量、登录 IP 与时长、按键点击行为及名下优惠券资产。
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            onClick={openBroadcastModal}
            className="tactile inline-flex items-center gap-1.5 rounded-lg border border-violet-600 bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-violet-700 transition"
          >
            <Megaphone size={14} weight="bold" />
            <span>主动推送通知</span>
          </button>
          <button
            type="button"
            onClick={() => {
              void fetchStats();
              void fetchUsers();
              showToast("已刷新用户大盘与列表");
            }}
            disabled={loadingUsers || loadingStats}
            className="tactile inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-1.5 text-xs font-medium text-[color:var(--ink)] hover:border-[color:var(--ink)] transition disabled:opacity-50"
          >
            <ArrowClockwise size={14} className={loadingUsers ? "animate-spin" : ""} />
            <span>刷新数据</span>
          </button>
        </div>
      </div>

      {/* Top statistics overview cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm">
          <div className="flex items-center justify-between text-[color:var(--muted)]">
            <span className="text-xs font-medium">全站用户总量</span>
            <UsersThree size={18} className="text-violet-600" />
          </div>
          <p className="mono mt-2 text-2xl font-bold text-[color:var(--ink)]">
            {stats ? stats.total_users.toLocaleString() : "-"}
          </p>
          <div className="mt-2 text-[11px] text-[color:var(--muted)]">
            7日内活跃: <span className="font-semibold text-[color:var(--ink)]">{stats?.active_7d ?? 0}</span> 人
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm">
          <div className="flex items-center justify-between text-[color:var(--muted)]">
            <span className="text-xs font-medium">今日活跃用户</span>
            <User size={18} className="text-emerald-600" />
          </div>
          <p className="mono mt-2 text-2xl font-bold text-emerald-600">
            {stats ? stats.active_today.toLocaleString() : "-"}
          </p>
          <div className="mt-2 text-[11px] text-[color:var(--muted)]">
            今日产生登录或交互
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm">
          <div className="flex items-center justify-between text-[color:var(--muted)]">
            <span className="text-xs font-medium">当前实时在线</span>
            <div className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
            </div>
          </div>
          <p className="mono mt-2 text-2xl font-bold text-[color:var(--ink)]">
            {stats ? stats.online_now.toLocaleString() : "-"}
          </p>
          <div className="mt-2 text-[11px] text-[color:var(--muted)]">
            近 15 分钟内保持活跃
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm">
          <div className="flex items-center justify-between text-[color:var(--muted)]">
            <span className="text-xs font-medium">按钮总点击数</span>
            <Cursor size={18} className="text-sky-600" />
          </div>
          <p className="mono mt-2 text-2xl font-bold text-[color:var(--ink)]">
            {stats ? stats.total_clicks.toLocaleString() : "-"}
          </p>
          <div className="mt-2 text-[11px] text-[color:var(--muted)]">
            去购买/领券/订阅汇总
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-[color:var(--muted)]">
            <span className="text-xs font-medium">用户持有券总数</span>
            <Ticket size={18} className="text-amber-600" />
          </div>
          <p className="mono mt-2 text-2xl font-bold text-amber-600">
            {stats ? stats.total_coupons_held.toLocaleString() : "-"}
          </p>
          <div className="mt-2 text-[11px] text-[color:var(--muted)]">
            全站已分配至用户卡包
          </div>
        </div>
      </div>

      {/* Filter and search bar */}
      <div className="rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-sm">
        <form onSubmit={handleSearchSubmit} className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 items-center gap-2">
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索用户邮箱 / 昵称 / 登录 IP..."
                className="w-full rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--paper)] py-2 pl-9 pr-3 text-xs text-[color:var(--ink)] placeholder-[color:var(--muted)] outline-none focus:border-[color:var(--ink)] transition"
              />
            </div>
            <button
              type="submit"
              className="tactile shrink-0 rounded-lg bg-[color:var(--ink)] px-3 py-2 text-xs font-medium text-white transition hover:opacity-90"
            >
              检索
            </button>
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setAppliedQuery("");
                  setPage(1);
                }}
                className="text-xs text-[color:var(--muted)] hover:text-[color:var(--ink)] underline"
              >
                清除
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Status filter */}
            <div className="flex items-center gap-1">
              <span className="text-[color:var(--muted)]">状态:</span>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--paper)] px-2.5 py-1.5 text-xs text-[color:var(--ink)] outline-none"
              >
                <option value="all">全部用户</option>
                <option value="online">实时在线</option>
                <option value="offline">离线用户</option>
                <option value="active">正常账号</option>
                <option value="disabled">已禁用账号</option>
              </select>
            </div>

            {/* Sort by */}
            <div className="flex items-center gap-1">
              <span className="text-[color:var(--muted)]">排序:</span>
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--paper)] px-2.5 py-1.5 text-xs text-[color:var(--ink)] outline-none"
              >
                <option value="last_login">最近登录时间</option>
                <option value="duration">累计在线时长</option>
                <option value="clicks">按钮点击次数</option>
                <option value="created_at">注册时间</option>
              </select>
            </div>

            {/* Order toggle */}
            <button
              type="button"
              onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
              className="tactile rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--paper)] px-2.5 py-1.5 text-xs font-medium text-[color:var(--ink)]"
            >
              {order === "desc" ? "倒序 (高→低)" : "正序 (低→高)"}
            </button>
          </div>
        </form>
      </div>

      {/* Main Users Table */}
      <div className="overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[color:var(--ink)]">
            <thead className="border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] text-[11px] font-semibold text-[color:var(--muted)] uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">用户画像</th>
                <th className="px-3 py-3">机器人绑定</th>
                <th className="px-3 py-3">在线状态</th>
                <th className="px-3 py-3">登录时间</th>
                <th className="px-3 py-3">登录时长</th>
                <th className="px-3 py-3">登录 IP</th>
                <th className="px-3 py-3 text-center">按钮点击数</th>
                <th className="px-3 py-3 text-center">持券数量</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--line)]">
              {loadingUsers && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-xs text-[color:var(--muted)]">
                    <div className="inline-flex items-center gap-2">
                      <ArrowClockwise size={16} className="animate-spin text-violet-600" />
                      <span>正在加载用户数据...</span>
                    </div>
                  </td>
                </tr>
              )}

              {!loadingUsers && users.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-xs text-[color:var(--muted)]">
                    暂未匹配到符合条件的用户数据
                  </td>
                </tr>
              )}

              {!loadingUsers &&
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-[color:var(--surface)] transition-colors">
                    {/* User profile */}
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="grid h-8 w-8 place-items-center rounded-full bg-violet-100 text-violet-700 font-bold shrink-0 overflow-hidden">
                          {u.avatar_url ? (
                            <img src={u.avatar_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            u.nickname.slice(0, 1).toUpperCase()
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-sm truncate max-w-[140px] text-[color:var(--ink)]">
                              {u.nickname}
                            </span>
                            {u.has_qq_bound && (
                              <span className="inline-flex items-center rounded px-1.5 py-0.2 text-[10px] font-semibold bg-sky-100 text-sky-800 border border-sky-200">
                                QQ已绑
                              </span>
                            )}
                          </div>
                          <p className="mono text-[11px] text-[color:var(--muted)] truncate max-w-[170px]">
                            {u.email || `用户 ID: #${u.id}`}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Bot binding status */}
                    <td className="px-3 py-3.5">
                      {u.has_bot_bound ? (
                        <div className="flex flex-col gap-0.5 items-start">
                          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            <Robot size={13} weight="bold" />
                            <span>已绑定</span>
                          </span>
                          {u.bot_target_id && (
                            <span className="mono text-[10px] text-[color:var(--muted)] truncate max-w-[110px]" title={u.bot_target_id}>
                              {u.bot_channel?.toUpperCase() || "QQ"}: {u.bot_target_id.length > 10 ? `${u.bot_target_id.slice(0, 8)}...` : u.bot_target_id}
                            </span>
                          )}
                        </div>
                      ) : u.bot_target_id ? (
                        <div className="flex flex-col gap-0.5 items-start">
                          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200" title="已绑定但未开启或已停用">
                            <Robot size={13} />
                            <span>已停用</span>
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[color:var(--muted)] opacity-60">
                          未绑定
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="px-3 py-3.5">
                      <div className="flex flex-col gap-1 items-start">
                        {u.is_online ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            <span>在线</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--subtle)] border border-[color:var(--line)] px-2 py-0.5 text-[11px] font-medium text-[color:var(--muted)]">
                            <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                            <span>离线</span>
                          </span>
                        )}

                        {!u.is_active && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.2 text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                            已封禁
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Login Time */}
                    <td className="px-3 py-3.5">
                      <div>
                        <div className="flex items-center gap-1 text-[color:var(--ink)] font-medium">
                          <Clock size={13} className="text-[color:var(--muted)]" />
                          <span>{formatRelativeTime(u.last_login_at)}</span>
                        </div>
                        <p className="mono text-[10px] text-[color:var(--muted)] mt-0.5">
                          {formatDateTime(u.last_login_at)}
                        </p>
                      </div>
                    </td>

                    {/* Login Duration */}
                    <td className="px-3 py-3.5">
                      <div>
                        <div className="font-semibold text-violet-700">
                          {formatDuration(u.session_duration_seconds || 0)}
                        </div>
                        <p className="text-[10px] text-[color:var(--muted)] mt-0.5">
                          累计: {formatDuration(u.total_duration_seconds || 0)}
                        </p>
                      </div>
                    </td>

                    {/* Login IP */}
                    <td className="px-3 py-3.5">
                      {u.last_login_ip ? (
                        <div className="flex items-center gap-1">
                          <Globe size={13} className="text-[color:var(--muted)] shrink-0" />
                          <span className="mono text-xs font-medium text-[color:var(--ink)] truncate max-w-[110px]">
                            {u.last_login_ip}
                          </span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(u.last_login_ip, "IP 地址")}
                            className="text-[color:var(--muted)] hover:text-violet-600 transition p-0.5"
                            title="复制 IP"
                          >
                            {copiedText === u.last_login_ip ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                          </button>
                        </div>
                      ) : (
                        <span className="text-[color:var(--muted)] text-[11px]">-</span>
                      )}
                    </td>

                    {/* Button Clicks */}
                    <td className="px-3 py-3.5 text-center">
                      <span className="inline-flex items-center gap-1 rounded-md border border-[color:var(--line)] bg-[color:var(--paper)] px-2 py-1 mono font-semibold text-xs text-[color:var(--ink)]">
                        <Cursor size={12} className="text-sky-600" />
                        <span>{u.button_click_count || 0} 次</span>
                      </span>
                    </td>

                    {/* Coupon Count */}
                    <td className="px-3 py-3.5 text-center">
                      <button
                        type="button"
                        onClick={() => openUserDetail(u.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50/70 hover:bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900 transition"
                      >
                        <Ticket size={13} className="text-amber-700" />
                        <span>{u.coupon_count || 0} 张</span>
                        {u.active_coupon_count > 0 && (
                          <span className="text-[10px] text-emerald-700 font-bold">({u.active_coupon_count}可用)</span>
                        )}
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => openUserDetail(u.id)}
                          className="tactile inline-flex items-center gap-1 rounded-md border border-[color:var(--line-strong)] bg-[color:var(--paper)] px-2.5 py-1 text-[11px] font-medium text-[color:var(--ink)] hover:border-[color:var(--ink)] transition"
                        >
                          <Eye size={12} />
                          <span>详情</span>
                        </button>

                        <button
                          type="button"
                          disabled={togglingStatusId === u.id}
                          onClick={() => toggleUserStatus(u.id, u.is_active)}
                          className={`tactile inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
                            u.is_active
                              ? "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                              : "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          }`}
                        >
                          {u.is_active ? <EyeSlash size={12} /> : <Check size={12} />}
                          <span>{u.is_active ? "封禁" : "解封"}</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination footer */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-4 py-3 text-xs text-[color:var(--muted)]">
          <div>
            共 <span className="mono font-semibold text-[color:var(--ink)]">{total}</span> 位用户，当前第{" "}
            <span className="mono font-semibold text-[color:var(--ink)]">{page}</span> /{" "}
            <span className="mono font-semibold text-[color:var(--ink)]">{totalPages}</span> 页
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={page <= 1 || loadingUsers}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="tactile rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-2.5 py-1 text-xs font-medium text-[color:var(--ink)] disabled:opacity-40"
            >
              上一页
            </button>
            <span className="mono px-2 py-1">{page}</span>
            <button
              type="button"
              disabled={page >= totalPages || loadingUsers}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="tactile rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-2.5 py-1 text-xs font-medium text-[color:var(--ink)] disabled:opacity-40"
            >
              下一页
            </button>

            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setPage(1);
              }}
              className="ml-2 rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-2 py-1 text-xs text-[color:var(--ink)] outline-none"
            >
              <option value="10">10 条/页</option>
              <option value="20">20 条/页</option>
              <option value="50">50 条/页</option>
            </select>
          </div>
        </div>
      </div>

      {/* User Detail Modal / Drawer */}
      {selectedUserId !== null && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200"
        >
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm"
            onClick={closeUserDetail}
          />

          <div
            className="relative w-full max-w-3xl my-auto rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl z-10 max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-4">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-full bg-violet-100 text-violet-700 font-bold overflow-hidden shrink-0">
                  {userDetail?.user.avatar_url ? (
                    <img src={userDetail.user.avatar_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    userDetail?.user.nickname.slice(0, 1).toUpperCase() || "U"
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-[color:var(--ink)]">
                      {userDetail?.user.nickname || `用户 #${selectedUserId}`}
                    </h3>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        userDetail?.user.is_online
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-zinc-100 text-zinc-600"
                      }`}
                    >
                      {userDetail?.user.is_online ? "当前在线" : "离线"}
                    </span>
                    {!userDetail?.user.is_active && (
                      <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-800">
                        已封禁
                      </span>
                    )}
                  </div>
                  <p className="mono text-xs text-[color:var(--muted)]">
                    {userDetail?.user.email || "未绑定邮箱"} · 注册于{" "}
                    {formatDateTime(userDetail?.user.created_at || null)}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={closeUserDetail}
                className="grid h-8 w-8 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)]"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {/* User summary strip */}
            {userDetail && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 py-3 border-b border-[color:var(--line)] bg-[color:var(--surface)] px-3 my-3 rounded-lg text-xs">
                <div>
                  <span className="text-[color:var(--muted)]">本次/最近登录时长:</span>
                  <p className="font-semibold text-violet-700">
                    {formatDuration(userDetail.user.session_duration_seconds)}
                  </p>
                </div>
                <div>
                  <span className="text-[color:var(--muted)]">全站累计在线:</span>
                  <p className="font-semibold text-[color:var(--ink)]">
                    {formatDuration(userDetail.user.total_duration_seconds)}
                  </p>
                </div>
                <div>
                  <span className="text-[color:var(--muted)]">按钮点击总数:</span>
                  <p className="font-semibold text-sky-700">
                    {userDetail.user.button_click_count} 次
                  </p>
                </div>
                <div>
                  <span className="text-[color:var(--muted)]">持券情况:</span>
                  <p className="font-semibold text-amber-700">
                    {userDetail.coupons.length} 张 ({userDetail.user.active_coupon_count} 张可用)
                  </p>
                </div>
              </div>
            )}

            {/* Tab navigation within drawer */}
            <div className="flex items-center gap-2 border-b border-[color:var(--line)] pb-2 mb-3">
              {[
                { id: "sessions" as const, label: "登录与会话历史", count: userDetail?.sessions.length ?? 0 },
                { id: "coupons" as const, label: "名下优惠券卡包", count: userDetail?.coupons.length ?? 0 },
                { id: "logs" as const, label: "按钮点击与操作日志", count: userDetail?.action_logs.length ?? 0 },
                { id: "bot" as const, label: "机器人绑定", count: userDetail?.bot_bindings?.length ?? (userDetail?.user.has_bot_bound ? 1 : 0) },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setDetailTab(t.id)}
                  className={`tactile inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    detailTab === t.id
                      ? "bg-[color:var(--ink)] text-white"
                      : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                  }`}
                >
                  <span>{t.label}</span>
                  <span className="mono text-[10px] opacity-75">({t.count})</span>
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto pr-1">
              {loadingDetail && (
                <div className="py-16 text-center text-xs text-[color:var(--muted)]">
                  <ArrowClockwise size={18} className="animate-spin text-violet-600 mx-auto mb-2" />
                  <span>正在加载用户详情...</span>
                </div>
              )}

              {/* Tab 1: Sessions */}
              {!loadingDetail && detailTab === "sessions" && (
                <div className="space-y-2 text-xs">
                  {userDetail?.sessions.length === 0 ? (
                    <p className="py-8 text-center text-[color:var(--muted)]">暂无登录会话记录</p>
                  ) : (
                    userDetail?.sessions.map((s, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-[color:var(--line)] bg-[color:var(--paper)] p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="mono font-semibold text-[color:var(--ink)]">{s.ip_address || "未知 IP"}</span>
                            <span
                              className={`rounded px-1.5 py-0.2 text-[10px] font-medium ${
                                s.is_active ? "bg-emerald-100 text-emerald-800" : "bg-zinc-100 text-zinc-600"
                              }`}
                            >
                              {s.is_active ? "会话有效" : "已过期/退出"}
                            </span>
                          </div>
                          <p className="mono text-[11px] text-[color:var(--muted)] mt-1 truncate max-w-md">
                            {s.user_agent || "未知客户端环境"}
                          </p>
                        </div>
                        <div className="text-right sm:self-center shrink-0">
                          <p className="font-semibold text-violet-700">{formatDuration(s.duration_seconds)}</p>
                          <p className="text-[10px] text-[color:var(--muted)] mt-0.5">
                            登录于 {formatDateTime(s.created_at)}
                          </p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 2: Coupons */}
              {!loadingDetail && detailTab === "coupons" && (
                <div className="space-y-2 text-xs">
                  {userDetail?.coupons.length === 0 ? (
                    <p className="py-8 text-center text-[color:var(--muted)]">该用户暂未领取任何优惠券</p>
                  ) : (
                    userDetail?.coupons.map((c) => (
                      <div
                        key={c.id}
                        className="rounded-lg border border-[color:var(--line)] bg-[color:var(--paper)] p-3 flex items-center justify-between"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[color:var(--ink)]">{c.name}</span>
                            <span className="mono rounded bg-amber-100 px-1.5 py-0.2 text-[10px] font-bold text-amber-900 border border-amber-200">
                              券码: {c.code}
                            </span>
                          </div>
                          <p className="text-[11px] text-[color:var(--muted)] mt-1">
                            所属店铺: {c.shop_name} · 满 {c.min_spend} 减 {c.discount_amount} 元 · 到期时间:{" "}
                            {formatDateTime(c.expires_at)}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          {c.is_used ? (
                            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600">
                              已核销
                            </span>
                          ) : c.expires_at && new Date(c.expires_at).getTime() < Date.now() ? (
                            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-700">
                              已过期
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
                              未使用 (可用)
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 3: Action Logs */}
              {!loadingDetail && detailTab === "logs" && (
                <div className="space-y-1.5 text-xs">
                  {userDetail?.action_logs.length === 0 ? (
                    <p className="py-8 text-center text-[color:var(--muted)]">暂无操作流水记录</p>
                  ) : (
                    userDetail?.action_logs.map((l) => (
                      <div
                        key={l.id}
                        className="rounded-md border border-[color:var(--line)] bg-[color:var(--paper)] px-3 py-2 flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-sky-100 px-1.5 py-0.2 text-[10px] font-semibold text-sky-800">
                            {l.action_type}
                          </span>
                          <span className="font-semibold text-[color:var(--ink)]">{l.action_name}</span>
                          {l.page && <span className="text-[11px] text-[color:var(--muted)]">({l.page})</span>}
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-[color:var(--muted)]">
                          <span className="mono">{l.ip_address}</span>
                          <span>{formatDateTime(l.created_at)}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab 4: Bot Bindings */}
              {!loadingDetail && detailTab === "bot" && (
                <div className="space-y-3 text-xs">
                  {(!userDetail?.bot_bindings || userDetail.bot_bindings.length === 0) ? (
                    <div className="py-8 text-center text-[color:var(--muted)]">
                      <Robot size={36} className="mx-auto mb-2 opacity-40 text-indigo-600" />
                      <p className="font-semibold text-[color:var(--ink)]">该用户尚未绑定机器人</p>
                      <p className="text-[11px] text-[color:var(--muted)] mt-1">
                        用户可在个人中心「消息通知」中绑定 QQ 机器人接收降价与公告推送。
                      </p>
                    </div>
                  ) : (
                    userDetail.bot_bindings.map((b) => (
                      <div
                        key={b.id}
                        className="rounded-xl border border-[color:var(--line)] bg-[color:var(--paper)] p-4 space-y-2.5"
                      >
                        <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-2.5">
                          <div className="flex items-center gap-2">
                            <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-100 text-indigo-700">
                              <Robot size={18} weight="bold" />
                            </span>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-sm text-[color:var(--ink)]">
                                  {b.channel?.toUpperCase() || "QQ"} 机器人
                                </span>
                                {b.is_active ? (
                                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
                                    激活生效中
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600">
                                    已停用 / 暂停
                                  </span>
                                )}
                              </div>
                              <p className="mono text-[11px] text-[color:var(--muted)]">
                                目标标识 (Target ID): {b.target_id || "未填写"}
                              </p>
                            </div>
                          </div>
                          <span className="text-[10px] text-[color:var(--muted)]">
                            绑定于 {formatDateTime(b.created_at)}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px] bg-[color:var(--surface)] p-2.5 rounded-lg">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[color:var(--muted)]">降价提醒通知:</span>
                            <span className={b.notify_price_drop ? "text-emerald-700 font-semibold" : "text-zinc-500"}>
                              {b.notify_price_drop ? "已开启" : "已关闭"}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[color:var(--muted)]">涨价变动通知:</span>
                            <span className={b.notify_price_hike ? "text-emerald-700 font-semibold" : "text-zinc-500"}>
                              {b.notify_price_hike ? "已开启" : "已关闭"}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Modal footer */}
            <div className="flex items-center justify-between border-t border-[color:var(--line)] pt-3 mt-3">
              <button
                type="button"
                onClick={() => userDetail && toggleUserStatus(userDetail.user.id, userDetail.user.is_active)}
                className={`tactile inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  userDetail?.user.is_active
                    ? "border border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100"
                    : "border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                }`}
              >
                {userDetail?.user.is_active ? <EyeSlash size={14} /> : <Check size={14} />}
                <span>{userDetail?.user.is_active ? "封禁该账号" : "解除封禁"}</span>
              </button>

              <button
                type="button"
                onClick={closeUserDetail}
                className="tactile rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-4 py-1.5 text-xs font-semibold text-[color:var(--ink)] hover:border-[color:var(--ink)]"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Broadcast Notification Modal */}
      {showBroadcastModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200"
        >
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShowBroadcastModal(false)}
          />

          <div
            className="relative w-full max-w-2xl my-auto rounded-2xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-6 shadow-2xl z-10 max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[color:var(--line)] pb-4">
              <div className="flex items-center gap-2.5">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-100 text-violet-700">
                  <Megaphone size={20} weight="bold" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-[color:var(--ink)]">全站主动推送通知</h3>
                  <p className="text-xs text-[color:var(--muted)]">
                    向已绑定邮箱或机器人的用户即时广播系统公告、降价动态或活动通知。
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowBroadcastModal(false)}
                className="grid h-8 w-8 place-items-center rounded-lg text-[color:var(--muted)] hover:bg-[color:var(--subtle)] hover:text-[color:var(--ink)]"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {/* Subtabs: 发起推送 vs 推送历史 */}
            <div className="flex items-center gap-2 border-b border-[color:var(--line)] pt-3 pb-2">
              <button
                type="button"
                onClick={() => setBroadcastSubTab("send")}
                className={`tactile inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  broadcastSubTab === "send"
                    ? "bg-[color:var(--ink)] text-white"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                <PaperPlaneTilt size={14} weight="bold" />
                <span>撰写并推送</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setBroadcastSubTab("history");
                  void fetchBroadcastHistory();
                }}
                className={`tactile inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  broadcastSubTab === "history"
                    ? "bg-[color:var(--ink)] text-white"
                    : "text-[color:var(--muted)] hover:text-[color:var(--ink)]"
                }`}
              >
                <Clock size={14} weight="bold" />
                <span>推送历史记录</span>
                {broadcastHistory.length > 0 && (
                  <span className="mono text-[10px] opacity-75">({broadcastHistory.length})</span>
                )}
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto py-4">
              {broadcastSubTab === "send" ? (
                <form onSubmit={handleSendBroadcast} className="space-y-4">
                  {/* Audience preview cards */}
                  <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-3.5">
                    <div className="flex items-center justify-between text-xs font-semibold text-violet-900 mb-2">
                      <div className="flex items-center gap-1.5">
                        <UsersThree size={16} className="text-violet-600" />
                        <span>预计触达用户覆盖面</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => void fetchBroadcastAudience()}
                        className="text-[11px] font-normal text-violet-700 hover:underline"
                      >
                        重新计算
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="rounded-lg bg-white/80 p-2 border border-violet-100">
                        <span className="text-[11px] text-[color:var(--muted)]">📧 绑定邮箱</span>
                        <p className="mono text-base font-bold text-[color:var(--ink)] mt-0.5">
                          {loadingAudience ? "-" : broadcastAudience?.email_users ?? 0}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white/80 p-2 border border-violet-100">
                        <span className="text-[11px] text-[color:var(--muted)]">🤖 绑定机器人</span>
                        <p className="mono text-base font-bold text-indigo-700 mt-0.5">
                          {loadingAudience ? "-" : broadcastAudience?.bot_users ?? 0}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white/80 p-2 border border-violet-100">
                        <span className="text-[11px] text-[color:var(--muted)]">👥 去重总触达</span>
                        <p className="mono text-base font-bold text-violet-700 mt-0.5">
                          {loadingAudience ? "-" : broadcastAudience?.total_reach ?? 0}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Channel selection */}
                  <div>
                    <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1.5">
                      推送渠道选择
                    </label>
                    <div className="flex items-center gap-4 text-xs">
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={broadcastEmail}
                          onChange={(e) => setBroadcastEmail(e.target.checked)}
                          className="h-4 w-4 rounded border-[color:var(--line-strong)] text-violet-600 focus:ring-violet-500"
                        />
                        <span className="flex items-center gap-1 font-medium text-[color:var(--ink)]">
                          <EnvelopeSimple size={14} className="text-sky-600" />
                          <span>电子邮件 (排入发送队列)</span>
                        </span>
                      </label>
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={broadcastBot}
                          onChange={(e) => setBroadcastBot(e.target.checked)}
                          className="h-4 w-4 rounded border-[color:var(--line-strong)] text-violet-600 focus:ring-violet-500"
                        />
                        <span className="flex items-center gap-1 font-medium text-[color:var(--ink)]">
                          <Robot size={14} className="text-indigo-600" />
                          <span>机器人私信 (QQ Bot 即时直发)</span>
                        </span>
                      </label>
                    </div>
                  </div>

                  {/* Title */}
                  <div>
                    <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1">
                      通知标题 <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="例如：【系统通知】Cursor 与 智谱 AI 比价专区正式上线！"
                      value={broadcastTitle}
                      onChange={(e) => setBroadcastTitle(e.target.value)}
                      className="w-full rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-xs text-[color:var(--ink)] placeholder-[color:var(--muted)] outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                    />
                  </div>

                  {/* Content */}
                  <div>
                    <label className="block text-xs font-semibold text-[color:var(--ink)] mb-1">
                      通知正文内容 <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      required
                      rows={5}
                      placeholder="输入通知详细内容，支持换行排版。邮件将自动附加您的官网署名与退订指引，机器人将以精简卡片方式发送。"
                      value={broadcastContent}
                      onChange={(e) => setBroadcastContent(e.target.value)}
                      className="w-full rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3 py-2 text-xs text-[color:var(--ink)] placeholder-[color:var(--muted)] outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                    />
                  </div>

                  {/* Submit bar */}
                  <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowBroadcastModal(false)}
                      className="tactile rounded-lg border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-4 py-2 text-xs font-semibold text-[color:var(--ink)] hover:border-[color:var(--ink)]"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      disabled={sendingBroadcast}
                      className="tactile inline-flex items-center gap-1.5 rounded-lg border border-violet-600 bg-violet-600 px-5 py-2 text-xs font-semibold text-white hover:bg-violet-700 transition disabled:opacity-50"
                    >
                      <PaperPlaneTilt size={14} className={sendingBroadcast ? "animate-pulse" : ""} />
                      <span>{sendingBroadcast ? "正在执行全网广播..." : "确认并立即推送"}</span>
                    </button>
                  </div>
                </form>
              ) : (
                /* History Tab */
                <div className="space-y-3">
                  {loadingBroadcastHistory && (
                    <div className="py-12 text-center text-xs text-[color:var(--muted)]">
                      <ArrowClockwise size={16} className="animate-spin text-violet-600 mx-auto mb-1.5" />
                      <span>正在获取历史记录...</span>
                    </div>
                  )}

                  {!loadingBroadcastHistory && broadcastHistory.length === 0 && (
                    <div className="py-12 text-center text-xs text-[color:var(--muted)]">
                      暂无推送记录，您可以在上方发起第一条广播。
                    </div>
                  )}

                  {!loadingBroadcastHistory &&
                    broadcastHistory.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-xl border border-[color:var(--line)] bg-[color:var(--paper)] p-3.5 text-xs space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[color:var(--ink)] text-sm">
                            {item.title}
                          </span>
                          <span className="mono text-[10px] text-[color:var(--muted)]">
                            {formatDateTime(item.created_at)}
                          </span>
                        </div>
                        <p className="text-[color:var(--muted)] whitespace-pre-wrap leading-relaxed line-clamp-3">
                          {item.content}
                        </p>
                        <div className="flex flex-wrap items-center justify-between border-t border-[color:var(--line)] pt-2 text-[11px] text-[color:var(--muted)]">
                          <div className="flex items-center gap-2">
                            <span>渠道:</span>
                            {item.channels.map((ch) => (
                              <span key={ch} className="rounded bg-[color:var(--surface)] px-1.5 py-0.2 text-[10px] font-semibold text-[color:var(--ink)]">
                                {ch === "email" ? "📧 邮件" : ch === "bot" ? "🤖 机器人" : ch}
                              </span>
                            ))}
                          </div>
                          <div className="flex items-center gap-3">
                            <span>触达用户: <strong className="text-[color:var(--ink)]">{item.target_user_count}</strong></span>
                            <span>邮件入队: <strong className="text-sky-700">{item.email_sent_count}</strong></span>
                            <span>机器人私信: <strong className="text-indigo-700">{item.bot_sent_count}</strong></span>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
