import { cache } from "react";
import { SITE_ID, siteApiPath } from "./brands";

export type SiteSettings = {
  configured: boolean; notice_title: string; notice_content: string; notice_link: string;
  advertise_enabled: boolean; ad_slots_enabled: boolean; relay_hub_enabled: boolean;
  google_verification: string; bing_verification: string; baidu_verification: string;
  ga_measurement_id: string; baidu_analytics_id: string;
};
export type Article = {
  id: number; site_id: string; slug: string; title: string; summary: string; category: string;
  author: string; markdown?: string; seo_title: string; seo_description: string;
  status: "draft" | "published"; published_at: string | null; updated_at: string;
};
export type ArticlePage = { items: Article[]; total: number; page: number; page_size: number };
const base = process.env.INTERNAL_API_BASE_URL || "http://127.0.0.1:8000";
export async function siteFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${siteApiPath(path)}`, { cache: "no-store", signal: AbortSignal.timeout(6000) });
  if (!response.ok) throw new Error(`Site ${SITE_ID} content ${path}: ${response.status}`);
  return response.json();
}
export const getSiteSettings = cache(() => siteFetch<SiteSettings>("/settings"));
export const getArticles = (page = 1, pageSize = 24) => siteFetch<ArticlePage>(`/articles?page=${page}&page_size=${pageSize}`);
export const getArticle = cache(async (slug: string): Promise<Article | null> => {
  const response = await fetch(`${base}${siteApiPath(`/articles/${encodeURIComponent(slug)}`)}`, { cache: "no-store", signal: AbortSignal.timeout(6000) });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Article read failed: ${response.status}`);
  return response.json();
});
