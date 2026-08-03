import type { Metadata } from "next";
import type { BrandSlug, GuideFaq } from "@/lib/guides/types";

const SITE_URL = "https://ai.pricememo.cn";

const BRAND_NAMES: Record<BrandSlug, string> = {
  openai: "OpenAI",
  claude: "Claude",
  gemini: "Gemini",
  grok: "Grok",
  x: "X",
};

export function guideMetadata(title: string, description: string, path: string): Metadata {
  const canonical = `${SITE_URL}${path}`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: "AI Price Radar",
      locale: "zh_CN",
      type: "article",
    },
  };
}

export function breadcrumbJsonLd(items: readonly { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: `${SITE_URL}${item.path}`,
    })),
  };
}

export function articleJsonLd(input: { title: string; description: string; path: string; dateModified: string }) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: input.title,
    description: input.description,
    dateModified: input.dateModified,
    inLanguage: "zh-CN",
    mainEntityOfPage: `${SITE_URL}${input.path}`,
    publisher: { "@type": "Organization", name: "AI Price Radar", url: SITE_URL },
  };
}

export function howToJsonLd(input: { title: string; description: string; steps: readonly string[] }) {
  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: input.title,
    description: input.description,
    step: input.steps.map((text, index) => ({
      "@type": "HowToStep",
      position: index + 1,
      name: `第 ${index + 1} 项`,
      text,
    })),
  };
}

export function faqJsonLd(items: readonly GuideFaq[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}

export { BRAND_NAMES, SITE_URL };
