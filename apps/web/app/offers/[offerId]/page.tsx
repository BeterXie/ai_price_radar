import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { QuoteDetails } from "@/components/brand-quotes";
import { getOffer } from "@/lib/api";
import { quoteBrand } from "@/lib/brand-quotes";
import { getContextualAds } from "@/lib/contextual-ads";
import { SITE_URL } from "@/lib/site";

type Props = { params: Promise<{ offerId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { offerId } = await params;
  const offer = await getOffer(offerId);
  return {
    title: offer ? `${offer.original_name} · ${offer.shop_name}` : "商品报价暂不可用",
    alternates: { canonical: `${SITE_URL}/offers/${encodeURIComponent(offerId)}` },
    robots: { index: false, follow: true },
  };
}

export default async function OfferPage({ params }: Props) {
  const { offerId } = await params;
  const offer = await getOffer(offerId);
  if (!offer) notFound();
  const slug = offer.product_slug || "";
  const ads = await getContextualAds(quoteBrand(slug));
  return <main id="main-content" className="shell py-8">
    <p className="mb-5 text-sm"><Link prefetch={false} href={slug ? `/products/${encodeURIComponent(slug)}` : "/products"}>← 查看同类商品比价</Link></p>
    <QuoteDetails quote={{ offer, slug, name: offer.product_name }} view="shops" filterQuery="" standalone sponsor={ads.detail} />
  </main>;
}
