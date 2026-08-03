import type { Metadata } from "next";
import type { BrandSlug, GeneralGuideSlug, KnownDeliveryType, ProductSlug } from "./types";

export type GuideCanonicalTarget =
  | { kind: "index" }
  | { kind: "brand"; slug: BrandSlug }
  | { kind: "product"; slug: ProductSlug }
  | { kind: "delivery"; slug: KnownDeliveryType }
  | { kind: "general"; slug: GeneralGuideSlug };

export function getGuideCanonicalPath(target: GuideCanonicalTarget): string {
  switch (target.kind) {
    case "index":
      return "/guides";
    case "brand":
      return `/guides/brands/${target.slug}`;
    case "product":
      return `/guides/products/${target.slug}`;
    case "delivery":
      return `/guides/delivery/${target.slug}`;
    case "general":
      return `/guides/${target.slug}`;
  }
}

export function createGuideMetadata(input: {
  title: string;
  description: string;
  canonicalPath: string;
  openGraphType?: "article" | "website";
}): Metadata {
  return {
    title: input.title,
    description: input.description,
    alternates: { canonical: input.canonicalPath },
    openGraph: {
      type: input.openGraphType ?? "article",
      title: input.title,
      description: input.description,
      url: input.canonicalPath,
    },
  };
}
