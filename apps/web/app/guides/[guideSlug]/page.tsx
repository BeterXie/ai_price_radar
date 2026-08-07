import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";
import { notFound } from "next/navigation";
import { GuideBlocks } from "@/components/guides/guide-blocks";
import { GuideJsonLd } from "@/components/guides/guide-json-ld";
import { GuideLayout } from "@/components/guides/guide-layout";
import { GuideSection } from "@/components/guides/guide-section";
import { GuideSources } from "@/components/guides/guide-sources";
import { generalGuides, getGeneralGuide } from "@/lib/guides/registry";
import type { GeneralGuideSlug, GuideBlock, GuideFaq } from "@/lib/guides/types";
import { articleJsonLd, breadcrumbJsonLd, faqJsonLd, guideMetadata, howToJsonLd } from "../_shared";

type PageProps = { params: Promise<{ guideSlug: string }> };

function blockLabel(block: GuideBlock, index: number) {
  if (block.type === "faq") return "常见问题";
  if (block.type === "paragraph") return index === 0 ? "先了解这些" : `补充说明 ${index + 1}`;
  if (block.title) return block.title;
  if (block.type === "steps") return "操作步骤";
  if (block.type === "checklist") return "检查清单";
  if (block.type === "comparison") return "对照说明";
  return "重要提示";
}

export function generateStaticParams() {
  return Object.values(generalGuides).map((guide) => ({ guideSlug: guide.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { guideSlug } = await params;
  const guide = getGeneralGuide(guideSlug as GeneralGuideSlug);
  if (!guide) return { title: "通用教程不存在", robots: { index: false, follow: true } };
  return guideMetadata(guide.title, guide.description, `/guides/${guide.slug}`);
}

export default async function GeneralGuidePage({ params }: PageProps) {
  const { guideSlug } = await params;
  const guide = getGeneralGuide(guideSlug as GeneralGuideSlug);
  if (!guide) notFound();

  const path = `/guides/${guide.slug}`;
  const faq = guide.blocks.flatMap((block) => block.type === "faq" ? block.items : []) as readonly GuideFaq[];
  const procedure = guide.blocks.find((block) => block.type === "steps" || block.type === "checklist");
  const procedureItems = procedure && (procedure.type === "steps" || procedure.type === "checklist") ? procedure.items : [];
  const toc = guide.blocks.map((block, index) => ({ id: `section-${index + 1}`, label: blockLabel(block, index) }));
  toc.push({ id: "sources", label: "官方来源" });
  const schemas: Record<string, unknown>[] = [
    breadcrumbJsonLd([
      { name: "首页", path: "/" },
      { name: "教程中心", path: "/guides" },
      { name: guide.title, path },
    ]),
    articleJsonLd({ title: guide.title, description: guide.description, path, dateModified: guide.lastReviewedAt }),
  ];
  if (procedureItems.length) schemas.push(howToJsonLd({ title: guide.title, description: guide.description, steps: procedureItems }));
  if (faq.length) schemas.push(faqJsonLd(faq));

  return (
    <>
      <GuideJsonLd data={schemas} />
      <GuideLayout
        breadcrumbs={[
          { href: "/", label: "首页" },
          { href: "/guides", label: "教程中心" },
          { label: guide.title },
        ]}
        title={guide.title}
        description={guide.description}
        lastReviewedAt={guide.lastReviewedAt}
        toc={toc}
        footer={
          <div className="flex flex-wrap gap-4">
            <Link href="/guides" className="tactile inline-flex min-h-11 items-center gap-2 rounded-[10px] bg-[color:var(--ink)] px-5 text-sm font-medium text-white">
              返回教程中心
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
            <Link href="/products" className="inline-flex min-h-11 items-center rounded-[10px] border border-[color:var(--line-strong)] px-5 text-sm font-medium">查看报价目录</Link>
          </div>
        }
      >
        {guide.blocks.map((block, index) => (
          <GuideSection key={index} id={`section-${index + 1}`} title={blockLabel(block, index)}>
            <GuideBlocks blocks={[block]} />
          </GuideSection>
        ))}
        <GuideSection id="sources" title="官方来源"><GuideSources sources={guide.officialSources} /></GuideSection>
      </GuideLayout>
    </>
  );
}
