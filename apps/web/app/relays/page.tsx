import type { Metadata } from "next";
import { RelayCatalogPage } from "@/components/relay-catalog-page";
import type { RawSearchParams } from "@/components/product-workspace";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "API 中转站目录｜模型覆盖、计费方式与入口",
  description: "AI 商品报价目录中的 API 中转站，展示模型覆盖、计费方式、可用性与真实接口采样结果。收录不构成推荐或担保。",
  alternates: { canonical: `${SITE_URL}/relays` },
  openGraph: {
    title: "API 中转站目录 · AI Price Memory",
    description: "公开 AI API 中转站的模型覆盖、计费方式与真实接口检测结果。",
    url: `${SITE_URL}/relays`,
    type: "website",
  },
};

export default async function RelaysPage({ searchParams }: { searchParams: Promise<RawSearchParams> }) {
  return <RelayCatalogPage rawParams={await searchParams} basePath="/relays" />;
}
