import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";
import { notFound } from "next/navigation";
import { GuideBlocks } from "@/components/guides/guide-blocks";
import { GuideCallout } from "@/components/guides/guide-callout";
import { GuideCard } from "@/components/guides/guide-card";
import { GuideChecklist } from "@/components/guides/guide-checklist";
import { GuideComparison } from "@/components/guides/guide-comparison";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { GuideLayout } from "@/components/guides/guide-layout";
import { GuideSection } from "@/components/guides/guide-section";
import { GuideSources } from "@/components/guides/guide-sources";
import { brandGuides, getBrandGuide, getDeliveryGuide, productGuides } from "@/lib/guides/registry";
import type { BrandSlug } from "@/lib/guides/types";
import { articleJsonLd, BRAND_NAMES, breadcrumbJsonLd, guideMetadata } from "../../_shared";

type PageProps = { params: Promise<{ brand: string }> };

export function generateStaticParams() {
  return Object.values(brandGuides).map((guide) => ({ brand: guide.brand }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { brand } = await params;
  const guide = getBrandGuide(brand as BrandSlug);
  if (!guide) return { title: "品牌教程不存在", robots: { index: false, follow: true } };
  return guideMetadata(guide.title, guide.description, `/guides/brands/${guide.brand}`);
}

export default async function BrandGuidePage({ params }: PageProps) {
  const { brand } = await params;
  const guide = getBrandGuide(brand as BrandSlug);
  if (!guide) notFound();

  const products = guide.productSlugs.map((slug) => productGuides[slug]);
  const deliveries = guide.commonDeliveryTypes.map((type) => getDeliveryGuide(type)).filter((item) => item !== undefined);
  const path = `/guides/brands/${guide.brand}`;
  const toc = [
    { id: "overview", label: "品牌简介" },
    { id: "products", label: "当前收录产品" },
    { id: "plans", label: "套餐选择" },
    { id: "account-api", label: "账号与 API" },
    { id: "delivery", label: "常见交付类型" },
    { id: "sources", label: "官方帮助入口" },
    { id: "risks", label: "风险提示" },
    { id: "offers", label: "相关报价" },
  ];

  return (
    <>
      <GuideJsonLd data={[
        breadcrumbJsonLd([
          { name: "首页", path: "/" },
          { name: "教程中心", path: "/guides" },
          { name: BRAND_NAMES[guide.brand], path },
        ]),
        articleJsonLd({ title: guide.title, description: guide.description, path, dateModified: guide.lastReviewedAt }),
      ]} />
      <GuideLayout
        breadcrumbs={[
          { href: "/", label: "首页" },
          { href: "/guides", label: "教程中心" },
          { label: BRAND_NAMES[guide.brand] },
        ]}
        title={guide.title}
        description={guide.description}
        lastReviewedAt={guide.lastReviewedAt}
        toc={toc}
        footer={
          <Link href={`/products?brand=${encodeURIComponent(BRAND_NAMES[guide.brand])}`} className="tactile flex min-h-12 items-center justify-between text-sm font-semibold">
            查看 {BRAND_NAMES[guide.brand]} 公开报价
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        }
      >
        <GuideSection id="overview" title="品牌简介"><GuideBlocks blocks={guide.overview} /></GuideSection>

        <GuideSection id="products" title="当前收录产品" intro="每个产品教程按稳定分类维护，不根据商品标题临时生成。">
          <div className="grid gap-4 sm:grid-cols-2">
            {products.map((product) => (
              <GuideCard key={product.productSlug} href={`/guides/products/${product.productSlug}`} title={product.title} description={product.description} meta={product.productSlug} />
            ))}
          </div>
        </GuideSection>

        <GuideSection id="plans" title="套餐选择" intro="套餐权益、用量与资格可能调整，购买前同时核对官方说明和商品原页面。">
          <GuideChecklist items={guide.planNotes} />
        </GuideSection>

        <GuideSection id="account-api" title="账号与 API 的区别">
          <GuideComparison
            columns={["比较项", "账号或网页订阅", "API 服务"]}
            rows={[
              ["使用入口", "品牌网页或官方客户端", "开发接口、SDK 或兼容工具"],
              ["计费口径", "套餐期限和账号权益", "请求用量、额度或账单"],
              ["安全重点", "邮箱、恢复渠道和 MFA 控制权", "密钥权限、额度限制和泄露处置"],
            ]}
          />
        </GuideSection>

        <GuideSection id="delivery" title="常见第三方交付类型" intro="同一品牌下的商品可能采用不同交付方式，交付方式决定控制权、使用步骤和风险。">
          <div className="grid gap-3 sm:grid-cols-2">
            {deliveries.map((delivery) => (
              <Link key={delivery.deliveryType} href={`/guides/delivery/${delivery.deliveryType}`} className="flex min-h-14 items-center justify-between rounded-[12px] border hairline bg-[color:var(--panel)] px-4 text-sm font-semibold hover:border-black">
                {delivery.shortLabel}
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
            ))}
          </div>
        </GuideSection>

        <GuideSection id="sources" title="官方登录和帮助入口"><GuideSources sources={guide.officialSources} /></GuideSection>

        <GuideSection id="risks" title="品牌相关风险提示">
          <GuideCallout tone="warning" title="购买前请逐项确认">
            <ul className="list-disc space-y-2 pl-5">{guide.riskNotes.map((note) => <li key={note}>{note}</li>)}</ul>
          </GuideCallout>
        </GuideSection>

        <GuideSection id="offers" title="对应商品报价入口" intro="报价目录展示公开价格、库存、交付方式和最近更新时间。教程不代表任何商家背书。">
          <Link href={`/products?brand=${encodeURIComponent(BRAND_NAMES[guide.brand])}`} className="tactile inline-flex min-h-11 items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-5 text-sm font-medium text-white">
            查看 {BRAND_NAMES[guide.brand]} 报价
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </GuideSection>
      </GuideLayout>
    </>
  );
}
