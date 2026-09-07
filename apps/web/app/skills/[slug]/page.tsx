import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getSkillDetail } from "@/lib/api";
import { SkillDetailView } from "@/components/skills/skill-detail-view";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const skill = await getSkillDetail(slug);
  if (!skill) {
    return {
      title: "技能不存在 - AI 技能实验室",
      robots: { index: false, follow: true },
    };
  }

  const canonical = `https://ai.pricememo.cn/skills/${encodeURIComponent(skill.slug)}`;
  return {
    title: `${skill.title} - AI 技能实验室`,
    description: skill.summary || skill.subtitle,
    alternates: { canonical },
    openGraph: {
      title: `${skill.title} - AI 技能实验室`,
      description: skill.summary || skill.subtitle,
      url: canonical,
      type: "article",
    },
    twitter: {
      card: "summary_large_image",
      title: `${skill.title} - AI 技能实验室`,
      description: skill.summary || skill.subtitle,
    },
  };
}

export default async function SkillDetailPage({ params }: Props) {
  const { slug } = await params;
  const skill = await getSkillDetail(slug);

  if (!skill) {
    notFound();
  }

  return <SkillDetailView skill={skill} />;
}
