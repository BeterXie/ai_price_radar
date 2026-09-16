import type {
  AuthSessionState,
  QQBotBindingStartResponse,
  UserBotBinding,
  UserProfileResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

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
  try {
    return await jsonFetch<AuthSessionState>("/api/v1/auth/me");
  } catch {
    return { authenticated: false, user: null, token: null };
  }
}

export async function requestEmailLoginCode(email: string): Promise<{ success: boolean; retry_after: number; message: string }> {
  return jsonFetch("/api/v1/auth/email/code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyEmailLoginCode(email: string, code: string): Promise<AuthSessionState> {
  return jsonFetch<AuthSessionState>("/api/v1/auth/email/verify", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export async function logout(): Promise<void> {
  await jsonFetch("/api/v1/auth/logout", { method: "POST" });
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

export async function manualConfirmQQBotBinding(bindCode: string, targetId: string): Promise<{ success: boolean; binding: UserBotBinding }> {
  return jsonFetch(`/api/v1/user/notifications/qq/confirm?bind_code=${encodeURIComponent(bindCode)}&target_id=${encodeURIComponent(targetId)}`, {
    method: "POST",
  });
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
