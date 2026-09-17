"use client";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

/**
 * Tracks a button click event in the backend for user activity and metrics.
 */
export async function trackButtonClick(
  buttonName: string,
  buttonId: string = "",
  extraData: Record<string, any> = {}
): Promise<void> {
  if (typeof window === "undefined") return;

  try {
    const page = window.location.pathname;
    await fetch(`${API}/api/v1/user/track-click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      keepalive: true,
      body: JSON.stringify({
        button_name: buttonName,
        button_id: buttonId,
        page,
        extra_data: extraData,
      }),
    });
  } catch {
    // Fail silently without disrupting user interaction
  }
}

/**
 * Initializes a background heartbeat timer for authenticated users.
 * Sends a heartbeat every 45s to accumulate online duration and refresh active timestamp.
 */
export function initUserHeartbeat(): () => void {
  if (typeof window === "undefined") return () => {};

  const sendHeartbeat = async () => {
    if (document.visibilityState !== "visible") return;
    try {
      await fetch(`${API}/api/v1/user/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });
    } catch {
      // Fail silently
    }
  };

  // Immediate ping on init
  void sendHeartbeat();

  const intervalId = setInterval(sendHeartbeat, 45000);

  const handleVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      void sendHeartbeat();
    }
  };

  document.addEventListener("visibilitychange", handleVisibilityChange);

  return () => {
    clearInterval(intervalId);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}
