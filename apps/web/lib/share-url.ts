import { SITE_URL } from "./site";

export const CAMPAIGN_QUERY_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content"] as const;

/** Share a public canonical page without copying a visitor's filters or private parameters. */
export function buildShareUrl(path: string): string {
  const url = new URL(path, SITE_URL);
  if (url.origin !== new URL(SITE_URL).origin || !/^\/(compare|skills)(\/|$)/.test(url.pathname)) {
    throw new Error("Only public comparison and skill pages can be shared here");
  }
  url.search = new URLSearchParams({
    utm_source: "pricememo",
    utm_medium: "share",
    utm_campaign: "reader_share",
  }).toString();
  url.hash = "";
  return url.href;
}
