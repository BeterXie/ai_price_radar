"use client";

import { useEffect, useState } from "react";
import { BAIDU_PREFERENCE_KEY, isBaiduAnalyticsEnabled, isBaiduTrackingAllowed } from "@/lib/analytics-preferences";

export function BaiduAnalyticsPreference() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isBaiduAnalyticsEnabled()) setEnabled(isBaiduTrackingAllowed());
  }, []);

  if (enabled === null) return null;

  function updatePreference() {
    try {
      window.localStorage.setItem(BAIDU_PREFERENCE_KEY, enabled ? "denied" : "granted");
    } catch {
      setError("浏览器未能保存设置，请允许本站保存设置后重试。");
      return;
    }
    // A full reload also unloads an SDK that was already running.
    window.location.reload();
  }

  return (
    <div className="mt-4">
      <p className="text-sm text-[color:var(--muted)]">当前浏览器：百度统计{enabled ? "已开启" : "已停用"}</p>
      <button type="button" onClick={updatePreference} className="button-secondary mt-3">
        {enabled ? "停用百度统计" : "开启百度统计"}
      </button>
      {error ? <p role="alert" className="mt-2 text-sm">{error}</p> : null}
    </div>
  );
}
