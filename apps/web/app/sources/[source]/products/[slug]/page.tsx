import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getProduct, getMeta } from "@/lib/api";
import { PageHero } from "@/components/page-shell";
import { OfferGroupTable } from "@/components/offer-table";

export const dynamic = "force-dynamic";

const SITE_URL = "https://ai.pricememo.cn";

// Human-readable overrides per source+slug combination
const PAGE_META: Record<string, Record<string, { title: string; description: string; h1: string }>> = {
  "16688": {
    "chatgpt-access-service": {
      title: "16688 Codex 接码与验证码服务报价",
      description:
        "查看 16688 公开店铺中的 Codex 接码、验证码、短信验证和辅助开通服务报价、库存与来源。",
      h1: "16688 Codex 接码与验证服务",
    },
    "codex-access": {
      title: "16688 Codex 账号与访问报价",
      description:
        "比较 16688 公开店铺中的 Codex 账号、访问服务、库存、交付方式、店铺和更新时间。",
      h1: "16688 Codex 账号与访问",
    },
    "chatgpt-plus": {
      title: "16688 ChatGPT Plus 报价",
      description: "查看 16688 公开店铺中的 ChatGPT Plus 报价、库存、交付方式和最近更新时间。",
      h1: "16688 ChatGPT Plus 报价",
    },
    "claude-pro": {
      title: "16688 Claude Pro 报价",
      description: "查看 16688 公开店铺中的 Claude Pro 报价、库存与来源。",
      h1: "16688 Claude Pro 报价",
    },
    "gemini-advanced": {
      title: "16688 Gemini Advanced 报价",
      description: "查看 16688 公开店铺中的 Gemini Advanced 报价、库存与来源。",
      h1: "16688 Gemini Advanced 报价",
    },
    "grok-super": {
      title: "16688 SuperGrok 报价",
      description: "查看 16688 公开店铺中的 SuperGrok 报价、库存与来源。",
      h1: "16688 SuperGrok 报价",
    },
  },
};

function getPageMeta(source: string, slug: string, productName: string) {
  return (
    PAGE_META[source]?.[slug] ?? {
      title: `${source} ${productName} 报价`,
      description: `查看 ${source} 公开店铺中的 ${productName} 报价、库存、交付方式和最近更新时间。`,
      h1: `${source} ${productName} 报价`,
    }
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ source: string; slug: string }>;
}): Promise<Metadata> {
  const { source, slug } = await params;
  const product = await getProduct(slug, `source_platform=${encodeURIComponent(source)}`);
  const pageMeta = getPageMeta(source, slug, product?.display_name ?? slug);
  const canonical = `${SITE_URL}/sources/${encodeURIComponent(source)}/products/${encodeURIComponent(slug)}`;
  const hasOffers = (product?.offer_count ?? 0) >= 2;

  return {
    title: pageMeta.title,
    description: pageMeta.description,
    alternates: { canonical },
    robots: { index: hasOffers, follow: true },
    openGraph: {
      title: pageMeta.title,
      description: pageMeta.description,
      url: canonical,
      type: "website",
    },
  };
}

export default async function SourceProductPage({
  params,
}: {
  params: Promise<{ source: string; slug: string }>;
}) {
  const { source, slug } = await params;

  // Validate source platform exists
  const apiMeta = await getMeta();
  if (!apiMeta.source_platforms.some((p) => p.id === source)) notFound();

  const product = await getProduct(slug, `source_platform=${encodeURIComponent(source)}`);
  if (!product || product.offer_count === 0) notFound();

  const pageMeta = getPageMeta(source, slug, product.display_name);

  return (
    <main id="main-content" className="shell">
      {/* Breadcrumb */}
      <nav aria-label="breadcrumb" className="text-sm text-black/40 mb-4 flex gap-1.5">
        <Link href="/" className="hover:text-black">首页</Link>
        <span>/</span>
        <Link href="/sources" className="hover:text-black">来源平台</Link>
        <span>/</span>
        <Link href={`/sources/${encodeURIComponent(source)}`} className="hover:text-black">{source}</Link>
        <span>/</span>
        <span className="text-black/70">{product.display_name}</span>
      </nav>

      <PageHero
        eyebrow={`${source} · ${product.display_name}`}
        title={pageMeta.h1}
      />

      {/* Stats */}
      <section className="mt-6 grid grid-cols-3 gap-4 rounded-xl border border-black/10 p-5">
        <div>
          <p className="text-2xl font-semibold">{product.offer_count}</p>
          <p className="text-xs text-black/50 mt-1">当前报价数</p>
        </div>
        <div>
          <p className="text-2xl font-semibold">{product.in_stock_count}</p>
          <p className="text-xs text-black/50 mt-1">有货数</p>
        </div>
        <div>
          <p className="text-2xl font-semibold">{product.source_count}</p>
          <p className="text-xs text-black/50 mt-1">涉及店铺</p>
        </div>
      </section>

      {/* Offers */}
      <section className="mt-8">
        <OfferGroupTable
          groups={product.offer_groups}
          productSlug={product.slug}
          totalCount={product.offer_group_count}
          snapshotId={product.snapshot_id}
          filterQuery={`source_platform=${encodeURIComponent(source)}`}
        />
      </section>

      {/* Back links */}
      <section className="mt-10 flex gap-4 text-sm">
        <Link href={`/products/${encodeURIComponent(slug)}`} className="underline text-black/60 hover:text-black">
          查看全平台 {product.display_name} 报价
        </Link>
        <Link href={`/sources/${encodeURIComponent(source)}`} className="underline text-black/60 hover:text-black">
          返回 {source} 来源总览
        </Link>
      </section>
    </main>
  );
}
