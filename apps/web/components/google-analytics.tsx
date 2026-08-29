"use client";

import Script from "next/script";
import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

type Gtag = (...args: unknown[]) => void;

declare global {
  interface Window {
    dataLayer: unknown[];
    gtag?: Gtag;
  }
}

const MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
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
    const haystack = `${url.hostname}${url.pathname}`;
    const match = AI_REFERRAL_RULES.find((rule) => rule.pattern.test(haystack));
    if (!match) return null;
    return { source: url.hostname, term: match.term, path: url.pathname || "/" };
  } catch {
    return null;
  }
}

function sendGtag(...args: unknown[]) {
  window.dataLayer = window.dataLayer || [];
  if (window.gtag) window.gtag(...args);
  else window.dataLayer.push(args);
}

export function GoogleAnalytics() {
  const pathname = usePathname();
  const referralChecked = useRef(false);

  useEffect(() => {
    if (!MEASUREMENT_ID) return;
    const referral = referralChecked.current ? null : getAiReferral(document.referrer);
    referralChecked.current = true;
    sendGtag("event", "page_view", {
      page_path: pathname || "/",
      page_title: document.title,
      ...(referral ? { ai_referral_source: referral.source, ai_referral_term: referral.term } : {}),
    });
    if (referral) {
      sendGtag("event", "ai_referral", {
        ai_referral_source: referral.source,
        ai_referral_term: referral.term,
        ai_referral_path: referral.path,
        referral_medium: "referral",
      });
    }
  }, [pathname]);

  if (!MEASUREMENT_ID) return null;
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
        gtag("config", ${measurementId}, { send_page_view: false });
      `}</Script>
    </>
  );
}
