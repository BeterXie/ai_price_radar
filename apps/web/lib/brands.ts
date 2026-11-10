export const BRANDS = {
  pricememo: { name: "AI Price Memory", wordmark: "AI Price Memory", url: "https://ai.pricememo.cn", theme: "paper", mark: "PM", tagline: "公开报价记录" },
  aiprice: { name: "AIPrice", wordmark: "AIPrice", url: "https://aiprice.si", theme: "precision", mark: "AI", tagline: "看清每一份订阅的价格" },
  aisi: { name: "AISI Plus", wordmark: "aisi.plus", url: "https://aisi.plus", theme: "editorial", mark: "+", tagline: "为日常找到合适的 AI" },
  pricein: { name: "PriceIn", wordmark: "PriceIn", url: "https://pricein.cc", theme: "market", mark: "pi", tagline: "好价格，先比较" },
  openprice: { name: "OpenPrice", wordmark: "openprice", url: "https://openprice.in", theme: "index", mark: "op", tagline: "公开价格，清楚比较" },
} as const;
export type SiteId = keyof typeof BRANDS;
export function resolveSiteId(value: string | undefined): SiteId {
  if (!value) return "pricememo";
  if (Object.hasOwn(BRANDS, value)) return value as SiteId;
  throw new Error(`Unknown NEXT_PUBLIC_SITE_ID: ${value}`);
}
export const SITE_ID = resolveSiteId(process.env.NEXT_PUBLIC_SITE_ID);
export const BRAND = BRANDS[SITE_ID];
export const IS_PRIMARY_SITE = SITE_ID === "pricememo";
export const siteApiPath = (path: string) => `/api/v1/sites/${SITE_ID}${path}`;
export const promoApiPath = (path: string) => IS_PRIMARY_SITE ? `/api/v1${path}` : siteApiPath(path);
