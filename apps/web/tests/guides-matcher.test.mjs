import assert from "node:assert/strict";
import test from "node:test";

import { guideRegistry } from "../lib/guides/registry.ts";
import { getGuideLinkLabel, isDeliveryType, isKnownDeliveryGuide, resolveGuideHref } from "../lib/guides/matcher.ts";
import { KNOWN_DELIVERY_TYPES } from "../lib/guides/types.ts";

test("delivery guards distinguish known guides from unknown and invalid values", () => {
  for (const deliveryType of KNOWN_DELIVERY_TYPES) {
    assert.equal(isDeliveryType(deliveryType), true, deliveryType);
    assert.equal(isKnownDeliveryGuide(deliveryType), true, deliveryType);
  }
  assert.equal(isDeliveryType("unknown"), true);
  assert.equal(isKnownDeliveryGuide("unknown"), false);
  assert.equal(isDeliveryType("mystery"), false);
  assert.equal(isDeliveryType(null), false);
});

test("every product-delivery combination follows the documented matching matrix", () => {
  for (const product of Object.values(guideRegistry.products)) {
    for (const deliveryType of KNOWN_DELIVERY_TYPES) {
      const expected = product.supportedDeliveryTypes.includes(deliveryType)
        ? `/guides/products/${product.productSlug}#delivery-${deliveryType}`
        : `/guides/delivery/${deliveryType}`;
      assert.equal(resolveGuideHref({ productSlug: product.productSlug, deliveryType }), expected, `${product.productSlug}:${deliveryType}`);
    }
  }
});

test("fallbacks prefer delivery, then known product, then buying checklist", () => {
  assert.equal(resolveGuideHref({ productSlug: "not-a-product", deliveryType: "team_seat" }), "/guides/delivery/team_seat");
  assert.equal(resolveGuideHref({ productSlug: "chatgpt-plus", deliveryType: "not-a-delivery" }), "/guides/products/chatgpt-plus");
  assert.equal(resolveGuideHref({ productSlug: "not-a-product", deliveryType: "not-a-delivery" }), "/guides/buying-checklist");
  assert.equal(resolveGuideHref({ productSlug: "chatgpt-plus", deliveryType: "unknown" }), "/guides/buying-checklist");
  assert.equal(resolveGuideHref({}), "/guides/buying-checklist");
});

test("link labels exactly match the product integration copy", () => {
  const expected = {
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
  for (const [deliveryType, label] of Object.entries(expected)) assert.equal(getGuideLinkLabel(deliveryType), label);
  assert.equal(getGuideLinkLabel("invalid"), expected.unknown);
});
