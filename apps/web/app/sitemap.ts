import type { MetadataRoute } from "next";
import { PRODUCT_SLUGS } from "@/lib/catalog";

const SITE_URL = "https://ai.pricememo.cn";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: SITE_URL, lastModified, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE_URL}/products`, lastModified, changeFrequency: "hourly", priority: 0.9 },
    ...PRODUCT_SLUGS.map((slug) => ({
      url: `${SITE_URL}/products/${slug}`,
      lastModified,
      changeFrequency: "hourly" as const,
      priority: 0.8,
    })),
  ];
}
