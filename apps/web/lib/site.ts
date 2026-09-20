const DEFAULT_SITE_URL = "https://ai.pricememo.cn";

export function normalizeSiteUrl(value: string | undefined): string {
  const raw = value?.trim() || DEFAULT_SITE_URL;
  try {
    const parsed = new URL(raw);
    const localHttp = parsed.protocol === "http:" && ["localhost", "127.0.0.1"].includes(parsed.hostname);
    if ((parsed.protocol !== "https:" && !localHttp) || parsed.username || parsed.password) {
      return DEFAULT_SITE_URL;
    }
    return parsed.origin;
  } catch {
    return DEFAULT_SITE_URL;
  }
}

export const SITE_URL = normalizeSiteUrl(process.env.NEXT_PUBLIC_SITE_URL);
