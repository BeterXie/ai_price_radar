import { BRAND, IS_PRIMARY_SITE } from "./brands";
export const BAIDU_PREFERENCE_KEY = "apr:analytics-consent:v2:baidu";

export function isBaiduAnalyticsEnabled(): boolean {
  return typeof window !== "undefined" && (window.location.hostname === new URL(BRAND.url).hostname || (IS_PRIMARY_SITE && window.location.hostname === "pricememo.cn"));
}

export function isBaiduTrackingAllowed(): boolean {
  if (!isBaiduAnalyticsEnabled()) return false;
  try {
    const choice = window.localStorage.getItem(BAIDU_PREFERENCE_KEY);
    if (choice === "denied") return false;
    if (choice === "granted") return true;
    // Preserve a refusal made when the old prompt included both services.
    return window.localStorage.getItem(`${BAIDU_PREFERENCE_KEY}:google`) !== "denied";
  } catch {
    // Do not bypass a saved refusal when browser storage cannot be read.
    return false;
  }
}
