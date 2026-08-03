import { getProductGuide } from "./registry";
import { KNOWN_DELIVERY_TYPES, type DeliveryType, type KnownDeliveryType } from "./types";

const knownDeliveryTypes = new Set<string>(KNOWN_DELIVERY_TYPES);

const GUIDE_LINK_LABELS: Record<DeliveryType, string> = {
  subscription_recharge: "查看充值和确认订阅教程",
  finished_account: "查看账号登录和安全教程",
  semi_finished_account: "查看首次登录和激活教程",
  team_seat: "查看加入团队工作区教程",
  card_code: "查看兑换码使用教程",
  api_credit: "查看 API Key 与额度教程",
  verification_service: "查看验证服务风险说明",
  shared_pool: "查看共享账号使用风险",
  relay_api: "查看第三方中转服务说明",
  trial_account: "查看短期体验账号说明",
  unknown: "查看购买前检查清单",
};

export function isDeliveryType(value?: string | null): value is DeliveryType {
  return value === "unknown" || isKnownDeliveryGuide(value);
}

export function isKnownDeliveryGuide(value?: string | null): value is KnownDeliveryType {
  return typeof value === "string" && knownDeliveryTypes.has(value);
}

export function resolveGuideHref(input: {
  productSlug?: string | null;
  deliveryType?: string | null;
}): string {
  const product = getProductGuide(input.productSlug);

  if (
    product
    && isDeliveryType(input.deliveryType)
    && input.deliveryType !== "unknown"
    && product.supportedDeliveryTypes.includes(input.deliveryType)
  ) {
    return `/guides/products/${product.productSlug}#delivery-${input.deliveryType}`;
  }

  if (input.deliveryType === "unknown") return "/guides/buying-checklist";

  if (isKnownDeliveryGuide(input.deliveryType)) {
    return `/guides/delivery/${input.deliveryType}`;
  }

  if (product) return `/guides/products/${product.productSlug}`;
  return "/guides/buying-checklist";
}

export function getGuideLinkLabel(deliveryType?: string | null): string {
  return isDeliveryType(deliveryType) ? GUIDE_LINK_LABELS[deliveryType] : GUIDE_LINK_LABELS.unknown;
}
