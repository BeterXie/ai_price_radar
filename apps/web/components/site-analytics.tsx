"use client";

import Script from "next/script";
import { Suspense, useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import { isBaiduTrackingAllowed } from "@/lib/analytics-preferences";
import { CAMPAIGN_QUERY_KEYS } from "@/lib/share-url";

type Gtag = (...args: unknown[]) => void;
type BaiduCommand = [string, ...unknown[]];

declare global {
  interface Window {
    dataLayer: unknown[];
    gtag?: Gtag;
    _hmt?: { push: (command: BaiduCommand) => unknown };
  }
}

const MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
const CONSENT_KEY = "apr:analytics-consent:v1";
const BAIDU_SITE_ID = "0abf0f3c54963dc5874f6a4ebcbfaf37";
const BAIDU_SCRIPT_ID = "baidu-tongji";
let lastBaiduPage: string | null = null;
type AnalyticsConsent = "unknown" | "granted" | "denied";
const ANALYTICS_QUERY_KEYS = new Set([
  "auto_delivery",
  "brand",
  "comparable",
  "delivery_type",
  "in_stock",
  "kind",
  "max_price",
  "min_price",
  "model",
  "page",
  "period",
  "platform",
  "product",
  "q",
  "sort",
  "source_platform",
  "tag",
  "updated_within_hours",
  "warranty",
]);

export function isAnalyticsPathAllowed(pathname: string | null): boolean {
  if (!pathname) return false;
  return !["/account", "/admin", "/auth", "/tools/json-to-cockpit"].some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}
const AI_REFERRAL_RULES = [
  { term: "chatgpt", pattern: /chatgpt/i },
  { term: "claude", pattern: /claude/i },
  { term: "bard", pattern: /bard/i },
  { term: "gemini", pattern: /gemini/i },
  { term: "perplexity", pattern: /perplexity/i },
  { term: "copilot", pattern: /copilot/i },
  { term: "poe", pattern: /(^|[./_-])poe([./_-]|$)/i },
  { term: "ai", pattern: /(^|[./_-])ai([./_-]|$)/i },
] as const;

function getAiReferral(referrer: string) {
  if (!referrer) return null;
  try {
    const url = new URL(referrer);
    if (!/^https?:$/.test(url.protocol) || url.origin === window.location.origin) return null;
    const match = AI_REFERRAL_RULES.find((rule) => rule.pattern.test(url.hostname));
    if (!match) return null;
    return { source: url.hostname, term: match.term };
  } catch {
    return null;
  }
}

export function buildAnalyticsPath(pathname: string | null, rawSearch: string, includeCampaign = true): string {
  const source = new URLSearchParams(rawSearch);
  const safeEntries: Array<[string, string]> = [];
  for (const [key, rawValue] of source.entries()) {
    if ((CAMPAIGN_QUERY_KEYS as readonly string[]).includes(key)) {
      // Accept compact public labels (including chatgpt.com), not email addresses or free text.
      if (includeCampaign && source.getAll(key).length === 1 && /^[a-z][a-z0-9._-]{0,39}$/.test(rawValue)) {
        safeEntries.push([key, rawValue]);
      }
      continue;
    }
    if (!ANALYTICS_QUERY_KEYS.has(key)) continue;
    if (key === "q") {
      if (rawValue.trim()) safeEntries.push([key, "present"]);
      continue;
    }
    if (key === "page") {
      if (/^\d{1,4}$/.test(rawValue) && Number(rawValue) > 0) safeEntries.push([key, rawValue]);
      continue;
    }
    const value = rawValue.trim();
    if (!value || value.length > 80 || /[&=#\u0000-\u001f\u007f]/.test(value)) continue;
    safeEntries.push([key, value]);
  }
  safeEntries.sort(([leftKey, leftValue], [rightKey, rightValue]) => (
    leftKey.localeCompare(rightKey) || leftValue.localeCompare(rightValue)
  ));
  const safeSearch = new URLSearchParams(safeEntries).toString();
  return `${pathname || "/"}${safeSearch ? `?${safeSearch}` : ""}`;
}

export function trackBaiduPageview(pathname: string | null, rawSearch: string, baiduId = BAIDU_SITE_ID): void {
  if (!baiduId || !isBaiduTrackingAllowed() || !isAnalyticsPathAllowed(pathname)) {
    lastBaiduPage = null;
    return;
  }

  const path = buildAnalyticsPath(pathname, rawSearch);
  const navigationPath = buildAnalyticsPath(pathname, rawSearch, false);
  const existingScript = document.getElementById(BAIDU_SCRIPT_ID);
  const queue = window._hmt || (window._hmt = [] as BaiduCommand[]);
  if (!existingScript) {
    // Configure before loading hm.js: the router sends the initial PV and later navigations.
    queue.push(["_setAutoPageview", false]);
    lastBaiduPage = null;
  }
  if (lastBaiduPage === navigationPath) return;
  queue.push(["_trackPageview", path]);
  lastBaiduPage = navigationPath;

  if (!existingScript) {
    const script = document.createElement("script");
    script.id = BAIDU_SCRIPT_ID;
    script.async = true;
    script.src = `https://hm.baidu.com/hm.js?${baiduId}`;
    document.head.appendChild(script);
  }
}

function sendGtag(...args: unknown[]) {
  window.dataLayer = window.dataLayer || [];
  if (window.gtag) window.gtag(...args);
  else window.dataLayer.push(args);
}

type AnalyticsProps = { measurementId?: string; baiduId?: string };
function SiteAnalyticsInner({ measurementId: MEASUREMENT_ID, baiduId }: AnalyticsProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const referralChecked = useRef(false);
  const lastGooglePage = useRef<string | null>(null);
  const [consent, setConsent] = useState<AnalyticsConsent | null>(null);
  const pathAllowed = isAnalyticsPathAllowed(pathname);
  const rawSearch = searchParams.toString();
  const analyticsPath = buildAnalyticsPath(pathname, rawSearch);
  const navigationPath = buildAnalyticsPath(pathname, rawSearch, false);

  useEffect(() => {
    if (!MEASUREMENT_ID) return;
    try {
      const stored = window.localStorage.getItem(CONSENT_KEY)
        ?? window.localStorage.getItem("apr:analytics-consent:v2:baidu:google");
      setConsent(stored === "granted" || stored === "denied" ? stored : "unknown");
    } catch {
      setConsent("unknown");
    }
  }, []);

  const updateConsent = (value: Exclude<AnalyticsConsent, "unknown">) => {
    try {
      window.localStorage.setItem(CONSENT_KEY, value);
    } catch {
      // Keep the in-memory choice for this page even when storage is blocked.
    }
    setConsent(value);
  };

  useEffect(() => {
    trackBaiduPageview(pathname, rawSearch, baiduId);
  }, [pathname, rawSearch, baiduId]);

  useEffect(() => {
    if (!MEASUREMENT_ID || consent !== "granted" || !pathAllowed) {
      lastGooglePage.current = null;
      return;
    }
    if (lastGooglePage.current === navigationPath) return;
    lastGooglePage.current = navigationPath;
    const referral = referralChecked.current ? null : getAiReferral(document.referrer);
    referralChecked.current = true;
    sendGtag("event", "page_view", {
      page_location: new URL(analyticsPath, window.location.origin).href,
      page_path: analyticsPath,
      page_title: document.title,
      ...(referral ? { ai_referral_source: referral.source, ai_referral_term: referral.term } : {}),
    });
    if (referral) {
      sendGtag("event", "ai_referral", {
        ai_referral_source: referral.source,
        ai_referral_term: referral.term,
        referral_medium: "referral",
      });
    }
  }, [analyticsPath, navigationPath, consent, pathAllowed]);

  if (!MEASUREMENT_ID) return null;
  if (!pathAllowed) return null;
  if (consent === null) return null;
  if (consent === "denied") return null;
  if (consent === "unknown") {
    return (
      <aside className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-xl border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-4 shadow-[0_18px_55px_rgba(18,19,15,.2)]" aria-label="分析服务选择">
        <p className="text-sm leading-6 text-[color:var(--ink)]">
          是否允许加载 Google Analytics，用于统计页面访问和 AI 引荐来源？拒绝不影响任何功能。详见
          <Link href="/privacy" className="ml-1 underline">隐私政策</Link>。
        </p>
        <div className="mt-3 flex justify-end gap-2">
          <button type="button" onClick={() => updateConsent("denied")} className="button-secondary tactile px-4 py-2 text-sm">
            拒绝
          </button>
          <button type="button" onClick={() => updateConsent("granted")} className="button-primary tactile px-4 py-2 text-sm">
            允许分析
          </button>
        </div>
      </aside>
    );
  }
  const measurementId = JSON.stringify(MEASUREMENT_ID).replace(/</g, "\\u003c");
  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(MEASUREMENT_ID)}`}
        strategy="afterInteractive"
      />
      <Script id="google-analytics-config" strategy="afterInteractive">{`
        window.dataLayer = window.dataLayer || [];
        function gtag(){window.dataLayer.push(arguments);}
        gtag("js", new Date());
        gtag("config", ${measurementId}, { send_page_view: false, anonymize_ip: true });
      `}</Script>
    </>
  );
}

export function SiteAnalytics({ measurementId = MEASUREMENT_ID, baiduId = BAIDU_SITE_ID }: AnalyticsProps = {}) {
  return (
    <Suspense fallback={null}>
      <SiteAnalyticsInner measurementId={measurementId} baiduId={baiduId} />
    </Suspense>
  );
}
