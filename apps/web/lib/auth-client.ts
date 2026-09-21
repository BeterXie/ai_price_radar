import type {
  AuthSessionState,
  CouponClaimResponse,
  CouponDropStatus,
  QQBotBindingStartResponse,
  UserBotBinding,
  UserCouponListOut,
  UserProfileResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

/**
 * Broadcast whenever the signed-in session changes (login, logout, QQ callback)
 * so shell components such as the site header refresh without a page reload.
 */
export const AUTH_CHANGE_EVENT = "ai-price-radar:auth-change";

function broadcastAuthChange(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

async function jsonFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    credentials: "include", // send cookies
  });
  if (!res.ok) {
    let errorDetail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) errorDetail = data.detail;
      else if (data?.message) errorDetail = data.message;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return (await res.json()) as T;
}

export async function fetchAuthMe(): Promise<AuthSessionState> {
  return jsonFetch<AuthSessionState>("/api/v1/auth/me");
}

export async function requestEmailLoginCode(email: string): Promise<{ success: boolean; retry_after: number; message: string }> {
  return jsonFetch("/api/v1/auth/email/code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyEmailLoginCode(email: string, code: string): Promise<AuthSessionState> {
  const session = await jsonFetch<AuthSessionState>("/api/v1/auth/email/verify", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
  if (session?.authenticated) {
    broadcastAuthChange();
  }
  return session;
}

export async function logout(): Promise<void> {
  await jsonFetch("/api/v1/auth/logout", { method: "POST" });
  // Drop the per-account watchlist cache so the next visitor to this browser
  // cannot see the previous user's list.
  clearCurrentUserWatchlistCache();
  broadcastAuthChange();
}

/** Email + password login for accounts that have set a password. */
export async function loginWithPassword(email: string, password: string): Promise<AuthSessionState> {
  const session = await jsonFetch<AuthSessionState>("/api/v1/auth/password/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (session?.authenticated) {
    broadcastAuthChange();
  }
  return session;
}

export interface PasswordUpdateResult {
  success: boolean;
  message: string;
  has_password: boolean;
}

/**
 * Set a login password (first time, e.g. right after the first email-code
 * login) or change the existing one (requires current_password).
 */
export async function setAccountPassword(input: {
  password: string;
  current_password?: string;
}): Promise<PasswordUpdateResult> {
  const result = await jsonFetch<PasswordUpdateResult>("/api/v1/user/password", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (result?.success) {
    broadcastAuthChange();
  }
  return result;
}

/**
 * Removes cached watchlist entries for the account that just logged out.
 * Kept here (rather than importing the component) to avoid a circular import.
 */
function clearCurrentUserWatchlistCache(): void {
  if (typeof window === "undefined") return;
  try {
    const prefix = "ai-price-radar:watchlist:v1:user:";
    const keysToRemove: string[] = [];
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (key && key.startsWith(prefix)) keysToRemove.push(key);
    }
    keysToRemove.forEach((key) => window.localStorage.removeItem(key));
    window.dispatchEvent(new Event("ai-price-radar:watchlist-change"));
  } catch {
    // Storage may be unavailable (private mode); nothing to clean.
  }
}

export async function fetchUserProfile(): Promise<UserProfileResponse> {
  return jsonFetch<UserProfileResponse>("/api/v1/user/profile");
}

export async function startQQBotBinding(): Promise<QQBotBindingStartResponse> {
  return jsonFetch<QQBotBindingStartResponse>("/api/v1/user/notifications/qq/start", {
    method: "POST",
  });
}

export async function checkQQBotBinding(sessionId: string): Promise<{ status: string; bind_code: string; target_id?: string; message?: string }> {
  return jsonFetch(`/api/v1/user/notifications/qq/status?session_id=${encodeURIComponent(sessionId)}`);
}

export async function updateQQNotificationPreferences(data: {
  is_active?: boolean;
  notify_price_drop?: boolean;
  notify_price_hike?: boolean;
}): Promise<UserBotBinding> {
  return jsonFetch<UserBotBinding>("/api/v1/user/notifications/qq", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function unbindQQBot(): Promise<void> {
  await jsonFetch("/api/v1/user/notifications/qq", {
    method: "DELETE",
  });
}

export async function bindCurrentLoggedInQQ(): Promise<{ success: boolean; binding: UserBotBinding }> {
  return jsonFetch("/api/v1/user/notifications/qq/bind-current", {
    method: "POST",
  });
}

export interface UserSubscriptionItem {
  id: number;
  product_slug: string;
  product_name: string;
  platform: string;
  target_price: string | null;
  current_min_price: string | null;
  current_currency: string;
  stock_count: number;
  notify_email: boolean;
  notify_bot: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserSubscriptionListResponse {
  items: UserSubscriptionItem[];
  count: number;
  email_bound: boolean;
  bot_bound: boolean;
}

export async function fetchUserSubscriptions(): Promise<UserSubscriptionListResponse> {
  return jsonFetch<UserSubscriptionListResponse>("/api/v1/user/subscriptions");
}

export interface UserSubscriptionSaveInput {
  product_slug: string;
  target_price?: string | null;
  notify_email?: boolean;
  notify_bot?: boolean;
}

/**
 * Create or update a subscription.
 *
 * The API endpoint is a full replace (missing fields fall back to server
 * defaults of target_price=null / notify_email=true / notify_bot=true), so a
 * partial update would silently reset the other settings. Callers that only
 * change one field should call {@link updateUserSubscription}, which merges the
 * current values first.
 */
export async function saveUserSubscription(payload: UserSubscriptionSaveInput): Promise<UserSubscriptionItem> {
  return jsonFetch<UserSubscriptionItem>("/api/v1/user/subscriptions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateUserSubscription(
  productSlug: string,
  changes: Omit<UserSubscriptionSaveInput, "product_slug">
): Promise<UserSubscriptionItem> {
  return jsonFetch<UserSubscriptionItem>(`/api/v1/user/subscriptions/${encodeURIComponent(productSlug)}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export async function deleteUserSubscription(slug: string): Promise<{ success: boolean }> {
  return jsonFetch<{ success: boolean }>(`/api/v1/user/subscriptions/${encodeURIComponent(slug)}`, {
    method: "DELETE",
  });
}

export async function fetchUserCoupons(): Promise<UserCouponListOut> {
  return jsonFetch<UserCouponListOut>("/api/v1/user/coupons");
}

export async function redeemCoupon(code: string): Promise<CouponClaimResponse> {
  return jsonFetch<CouponClaimResponse>("/api/v1/user/coupons/redeem", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function claimLuckyDrop(claimToken: string): Promise<CouponClaimResponse> {
  return jsonFetch<CouponClaimResponse>("/api/v1/user/coupons/claim-drop", {
    method: "POST",
    body: JSON.stringify({ claim_token: claimToken }),
  });
}

export async function fetchCouponDropStatus(): Promise<CouponDropStatus> {
  return jsonFetch<CouponDropStatus>("/api/v1/user/coupons/drop-status");
}

export async function recordCouponDropTrigger(page?: string): Promise<{ success: boolean; eligible: boolean; claim_token: string }> {
  return jsonFetch<{ success: boolean; eligible: boolean; claim_token: string }>("/api/v1/user/coupons/record-drop-trigger", {
    method: "POST",
    body: JSON.stringify({ page: page || "" }),
  });
}

