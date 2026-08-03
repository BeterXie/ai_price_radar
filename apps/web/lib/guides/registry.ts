import { brandGuideEntries } from "@/content/guides/brands";
import { deliveryGuideEntries } from "@/content/guides/delivery";
import { generalGuideEntries } from "@/content/guides/general";
import { productGuideEntries } from "@/content/guides/products";
import { workflowGuideEntries } from "@/content/guides/workflows";
import type {
  BrandGuide,
  BrandSlug,
  DeliveryGuide,
  GeneralGuide,
  GeneralGuideSlug,
  GuideRegistry,
  KnownDeliveryType,
  ProductGuide,
  ProductSlug,
  WorkflowGuide,
  WorkflowGuideSlug,
} from "./types";
import { validateGuideRegistry } from "./validation";

function indexBy<K extends PropertyKey, V>(items: readonly V[], keyOf: (item: V) => K, label: string): Record<K, V> {
  const result = {} as Record<K, V>;
  for (const item of items) {
    const key = keyOf(item);
    if (Object.prototype.hasOwnProperty.call(result, key)) throw new Error(`Duplicate ${label}: ${String(key)}`);
    result[key] = item;
  }
  return result;
}

export const brandGuides: Readonly<Record<BrandSlug, BrandGuide>> = indexBy(brandGuideEntries, (guide) => guide.brand, "brand guide");
export const productGuides: Readonly<Record<ProductSlug, ProductGuide>> = indexBy(productGuideEntries, (guide) => guide.productSlug, "product guide");
export const deliveryGuides: Readonly<Record<KnownDeliveryType, DeliveryGuide>> = indexBy(deliveryGuideEntries, (guide) => guide.deliveryType, "delivery guide");
export const generalGuides: Readonly<Record<GeneralGuideSlug, GeneralGuide>> = indexBy(generalGuideEntries, (guide) => guide.slug, "general guide");
export const workflowGuides: Readonly<Record<WorkflowGuideSlug, WorkflowGuide>> = indexBy(workflowGuideEntries, (guide) => guide.slug, "workflow guide");

export const guideRegistry: GuideRegistry = {
  brands: brandGuides,
  products: productGuides,
  delivery: deliveryGuides,
  general: generalGuides,
  workflows: workflowGuides,
};

validateGuideRegistry(guideRegistry);

export function getBrandGuide(slug?: string | null): BrandGuide | undefined {
  return slug ? brandGuides[slug as BrandSlug] : undefined;
}

export function getProductGuide(slug?: string | null): ProductGuide | undefined {
  return slug ? productGuides[slug as ProductSlug] : undefined;
}

export function getDeliveryGuide(type?: string | null): DeliveryGuide | undefined {
  return type ? deliveryGuides[type as KnownDeliveryType] : undefined;
}

export function getGeneralGuide(slug?: string | null): GeneralGuide | undefined {
  return slug ? generalGuides[slug as GeneralGuideSlug] : undefined;
}

export function getWorkflowGuide(
  slug?: string | null,
): WorkflowGuide | undefined {
  return slug ? workflowGuides[slug as WorkflowGuideSlug] : undefined;
}
