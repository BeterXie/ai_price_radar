"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Remains mounted through waiting/error states so a recovered feed appears. */
export function AlertRefresh() {
  const router = useRouter();
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === "visible") router.refresh(); };
    const timer = window.setInterval(refresh, 60_000);
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("popstate", refresh);
    window.addEventListener("pageshow", refresh);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("popstate", refresh); window.removeEventListener("pageshow", refresh); };
  }, [router]);
  return null;
}
