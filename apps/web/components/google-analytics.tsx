"use client";

import Script from "next/script";
import { Suspense, useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";

type Gtag = (...args: unknown[]) => void;

declare global {
  interface Window {
    dataLayer: unknown[];
    gtag?: Gtag;
  }
}

const MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
const CONSENT_KEY = "apr:analytics-consent:v1";
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
  if (!pathname) return true;
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

export function buildAnalyticsPath(pathname: string | null, rawSearch: string): string {
  const source = new URLSearchParams(rawSearch);
  const safeEntries: Array<[string, string]> = [];
  for (const [key, rawValue] of source.entries()) {
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

function sendGtag(...args: unknown[]) {
  window.dataLayer = window.dataLayer || [];
  if (window.gtag) window.gtag(...args);
  else window.dataLayer.push(args);
}

function GoogleAnalyticsInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const referralChecked = useRef(false);
  const [consent, setConsent] = useState<AnalyticsConsent | null>(null);
  const pathAllowed = isAnalyticsPathAllowed(pathname);
  const analyticsPath = buildAnalyticsPath(pathname, searchParams.toString());

  useEffect(() => {
    if (!MEASUREMENT_ID) return;
    try {
      const stored = window.localStorage.getItem(CONSENT_KEY);
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
    if (!MEASUREMENT_ID || consent !== "granted" || !pathAllowed) return;
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
  }, [analyticsPath, consent, pathAllowed]);

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

export function GoogleAnalytics() {
  return (
    <Suspense fallback={null}>
      <GoogleAnalyticsInner />
    </Suspense>
  );
}
