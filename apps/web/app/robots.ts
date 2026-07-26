import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/admin", "/api/v1/admin/"],
    },
    sitemap: "https://ai.pricememo.cn/sitemap.xml",
    host: "https://ai.pricememo.cn",
  };
}
