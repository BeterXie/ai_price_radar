"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function RelayRefresh() {
  const router = useRouter();
  const [seconds, setSeconds] = useState(60);
  const [refreshing, startTransition] = useTransition();

  useEffect(() => {
    let nextRefresh = Date.now() + 60_000;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((nextRefresh - Date.now()) / 1000));
      setSeconds(remaining);
      if (remaining === 0 && document.visibilityState === "visible") {
        nextRefresh = Date.now() + 60_000;
        startTransition(() => router.refresh());
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [router]);

  return <span className="text-xs text-[color:var(--muted)]">每小时探测 · {refreshing ? "刷新中…" : `${seconds} 秒后刷新页面`}</span>;
}
