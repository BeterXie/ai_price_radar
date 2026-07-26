import type { MetadataRoute } from "next";
import { PRODUCT_SLUGS } from "@/lib/catalog";

const SITE_URL = "https://ai.pricememo.cn";

function platformFor(slug: string) {
  if (slug.startsWith("claude-")) return "Claude";
  if (slug.startsWith("gemini-")) return "Gemini";
  if (slug.startsWith("grok-")) return "Grok";
  if (slug.startsWith("x-premium")) return "X";
  return "OpenAI";
}

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: SITE_URL, lastModified, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE_URL}/products`, lastModified, changeFrequency: "hourly", priority: 0.9 },
    { url: `${SITE_URL}/shops/submit`, lastModified, changeFrequency: "monthly", priority: 0.5 },
    ...PRODUCT_SLUGS.map((slug) => ({
      url: `${SITE_URL}/products?platform=${encodeURIComponent(platformFor(slug))}&product=${encodeURIComponent(slug)}`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.8,
    })),
  ];
}
