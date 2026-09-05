import assert from "node:assert/strict";
import test from "node:test";

import { getBrandGuide, getDeliveryGuide, getGeneralGuide, getProductGuide, getWorkflowGuide, guideRegistry } from "../lib/guides/registry.ts";
import { PRODUCT_SLUGS, KNOWN_DELIVERY_TYPES, BRAND_SLUGS, GENERAL_GUIDE_SLUGS, WORKFLOW_GUIDE_SLUGS } from "../lib/guides/types.ts";
import { validateGuideRegistry } from "../lib/guides/validation.ts";
import { getProductEvidenceSources } from "../lib/product-seo.ts";

const EXPECTED_MATRIX = {
  "chatgpt-account": ["finished_account", "semi_finished_account", "trial_account", "shared_pool", "verification_service"],
  "chatgpt-plus": ["subscription_recharge", "finished_account", "semi_finished_account", "card_code", "shared_pool", "trial_account"],
  "chatgpt-go": ["subscription_recharge", "finished_account", "card_code"],
  "chatgpt-k12": ["team_seat", "finished_account"],
  "chatgpt-pro-5x": ["subscription_recharge", "finished_account", "semi_finished_account", "shared_pool", "trial_account"],
  "chatgpt-pro-20x": ["subscription_recharge", "finished_account", "semi_finished_account", "shared_pool", "trial_account"],
  "chatgpt-pro": ["subscription_recharge", "finished_account", "semi_finished_account", "shared_pool", "trial_account"],
  "openai-api-credit": ["api_credit", "relay_api", "card_code"],
  "chatgpt-access-service": ["verification_service"],
  "codex-access": ["finished_account", "subscription_recharge", "team_seat"],
  "claude-pro": ["subscription_recharge", "finished_account", "semi_finished_account", "card_code"],
  "claude-account": ["finished_account", "semi_finished_account", "trial_account", "shared_pool", "verification_service"],
  "claude-api-access": ["api_credit", "relay_api"],
  "gemini-advanced": ["subscription_recharge", "finished_account", "card_code"],
  "gemini-account": ["finished_account", "semi_finished_account", "verification_service"],
  "gemini-api-access": ["api_credit", "relay_api"],
  "grok-super": ["subscription_recharge", "finished_account", "card_code"],
  "grok-account": ["finished_account", "semi_finished_account", "trial_account"],
  "grok-api-access": ["api_credit", "relay_api"],
  "x-premium-basic": ["subscription_recharge", "finished_account"],
  "x-premium": ["subscription_recharge", "finished_account"],
  "x-premium-plus": ["subscription_recharge", "finished_account"],
};

test("registry covers every required brand, product, delivery type, general guide, and workflow guide", () => {
  assert.deepEqual(Object.keys(guideRegistry.brands).sort(), [...BRAND_SLUGS].sort());
  assert.deepEqual(Object.keys(guideRegistry.products).sort(), [...PRODUCT_SLUGS].sort());
  assert.deepEqual(Object.keys(guideRegistry.delivery).sort(), [...KNOWN_DELIVERY_TYPES].sort());
  assert.deepEqual(Object.keys(guideRegistry.general).sort(), [...GENERAL_GUIDE_SLUGS].sort());
  assert.deepEqual(Object.keys(guideRegistry.workflows).sort(), [...WORKFLOW_GUIDE_SLUGS].sort());
  assert.equal("unknown" in guideRegistry.delivery, false);
  assert.doesNotThrow(() => validateGuideRegistry(guideRegistry));
});

test("all 22 products match the documented delivery matrix", () => {
  assert.equal(Object.keys(EXPECTED_MATRIX).length, 22);
  for (const [slug, expectedDeliveryTypes] of Object.entries(EXPECTED_MATRIX)) {
    assert.deepEqual(guideRegistry.products[slug].supportedDeliveryTypes, expectedDeliveryTypes, slug);
  }
});

test("every guide is reviewed on the release date and has HTTPS official sources", () => {
  const allGuides = [
    ...Object.values(guideRegistry.brands),
    ...Object.values(guideRegistry.products),
    ...Object.values(guideRegistry.delivery),
    ...Object.values(guideRegistry.general),
  ];
  for (const guide of allGuides) {
    assert.equal(guide.lastReviewedAt, "2026-08-03", guide.title);
    assert.ok(guide.officialSources.length > 0, guide.title);
    for (const source of guide.officialSources) assert.equal(new URL(source.url).protocol, "https:", source.url);
  }
});

test("product content includes required safety and maintenance sections", () => {
  for (const product of Object.values(guideRegistry.products)) {
    assert.ok(product.buyingChecklist.length > 0, product.productSlug);
    assert.ok(product.verificationChecklist.length > 0, product.productSlug);
    assert.ok(product.riskNotes.length > 0, product.productSlug);
    assert.ok(product.faq.length > 0, product.productSlug);
    assert.match(product.disclaimer, /不参与交易、支付、交付或售后/, product.productSlug);
  }

  for (const slug of ["openai-api-credit", "claude-api-access", "gemini-api-access", "grok-api-access"]) {
    const text = JSON.stringify(guideRegistry.products[slug]);
    assert.match(text, /API Key/i, slug);
    assert.match(text, /公开代码|前端|代码仓库/, slug);
    assert.match(text, /环境变量|密钥管理/, slug);
    assert.match(text, /撤销/, slug);
  }

  assert.match(JSON.stringify(guideRegistry.delivery.finished_account), /控制权/);
  assert.match(JSON.stringify(guideRegistry.delivery.finished_account), /隐私|敏感/);
  assert.match(JSON.stringify(guideRegistry.delivery.shared_pool), /敏感/);
  assert.match(JSON.stringify(guideRegistry.delivery.relay_api), /第三方.*处理|处理.*第三方/);
});

test("representative product guides include actionable walkthroughs", () => {
  for (const slug of ["chatgpt-plus", "codex-access"]) {
    const walkthrough = guideRegistry.products[slug].walkthrough;
    assert.ok(walkthrough, slug);
    assert.ok(walkthrough.steps.length >= 5, slug);
    for (const step of walkthrough.steps) {
      assert.ok(step.title.length > 0, `${slug}: step title`);
      assert.ok(step.action.length > 40, `${slug}: ${step.title} action`);
      assert.ok(step.result.length > 10, `${slug}: ${step.title} result`);
    }
  }

  const codexGuide = JSON.stringify(guideRegistry.products["codex-access"]);
  assert.match(codexGuide, /\/tools\/json-to-cockpit/);
  assert.match(codexGuide, /jlcodes99\/cockpit-tools\/releases/);
  assert.match(codexGuide, /批量导入/);
  assert.match(codexGuide, /启动 API/);
  assert.match(codexGuide, /恢复可见性/);
  assert.match(codexGuide, /%USERPROFILE%/);
  assert.doesNotMatch(codexGuide, /chatgpt\.com\/api\/auth\/session/);
});

test("validation rejects a duplicate product slug", () => {
  const duplicateRegistry = {
    ...guideRegistry,
    products: {
      ...guideRegistry.products,
      "chatgpt-account": guideRegistry.products["chatgpt-plus"],
    },
  };
  assert.throws(() => validateGuideRegistry(duplicateRegistry), /duplicate product slug: chatgpt-plus/);
});

test("content states safety boundaries without offering bypass instructions", () => {
  const content = JSON.stringify(guideRegistry);
  assert.doesNotMatch(content, /(?:如何|教你|步骤如下).{0,8}绕过|绕过.{0,8}(?:方法|配置示例)/);
  assert.doesNotMatch(content, /绝对稳定|永久不封/);
  assert.doesNotMatch(content, /请.{0,8}(提交|发送).{0,8}(密码|验证码|恢复码)/);
});

test("guide lookups reject prototype properties", () => {
  assert.equal(getBrandGuide("constructor"), undefined);
  assert.equal(getProductGuide("toString"), undefined);
  assert.equal(getDeliveryGuide("__proto__"), undefined);
  assert.equal(getGeneralGuide("constructor"), undefined);
  assert.equal(getWorkflowGuide("hasOwnProperty"), undefined);
});

test("every product has three distinct official evidence anchors", () => {
  for (const product of Object.values(guideRegistry.products)) {
    const brand = product.brand === "openai"
      ? "OpenAI"
      : product.brand === "x"
        ? "X"
        : product.brand[0].toUpperCase() + product.brand.slice(1);
    const sources = getProductEvidenceSources(brand, null, product.officialSources);
    assert.equal(sources.length, 3, product.productSlug);
    assert.equal(new Set(sources.map((source) => source.url)).size, 3, product.productSlug);
    for (const source of sources) assert.equal(new URL(source.url).protocol, "https:", source.url);
  }
});
