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
  const result = Object.create(null) as Record<K, V>;
  for (const item of items) {
    const key = keyOf(item);
    if (Object.prototype.hasOwnProperty.call(result, key)) throw new Error(`Duplicate ${label}: ${String(key)}`);
    result[key] = item;
  }
  return result;
}

function lookup<K extends PropertyKey, V>(record: Readonly<Record<K, V>>, key: string | null | undefined): V | undefined {
  return key && Object.prototype.hasOwnProperty.call(record, key) ? record[key as K] : undefined;
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
  return lookup(brandGuides, slug);
}

export function getProductGuide(slug?: string | null): ProductGuide | undefined {
  return lookup(productGuides, slug);
}

export function getDeliveryGuide(type?: string | null): DeliveryGuide | undefined {
  return lookup(deliveryGuides, type);
}

export function getGeneralGuide(slug?: string | null): GeneralGuide | undefined {
  return lookup(generalGuides, slug);
}

export function getWorkflowGuide(
  slug?: string | null,
): WorkflowGuide | undefined {
  return lookup(workflowGuides, slug);
}
