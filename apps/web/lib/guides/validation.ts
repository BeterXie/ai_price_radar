import {
  BRAND_SLUGS,
  GENERAL_GUIDE_SLUGS,
  KNOWN_DELIVERY_TYPES,
  PRODUCT_SLUGS,
  type GuideRegistry,
  type OfficialSource,
  type ProductGuide,
} from "./types";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Invalid guide registry: ${message}`);
}

function assertExactKeys(actual: readonly string[], expected: readonly string[], label: string): void {
  const actualSet = new Set(actual);
  assert(actual.length === expected.length, `${label} count must be ${expected.length}, received ${actual.length}`);
  for (const key of expected) assert(actualSet.has(key), `missing ${label}: ${key}`);
}

function assertUnique(values: readonly string[], label: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    assert(!seen.has(value), `duplicate ${label}: ${value}`);
    seen.add(value);
  }
}

function validateSources(sources: readonly OfficialSource[], label: string): void {
  assert(sources.length > 0, `${label} must include at least one official source`);
  for (const source of sources) {
    assert(source.title.trim(), `${label} has a source without a title`);
    assert(source.publisher.trim(), `${label} has a source without a publisher`);
    assert(source.lastCheckedAt.trim(), `${label} has a source without lastCheckedAt`);
    let url: URL;
    try {
      url = new URL(source.url);
    } catch {
      throw new Error(`Invalid guide registry: ${label} has an invalid source URL: ${source.url}`);
    }
    assert(url.protocol === "https:", `${label} source must use HTTPS: ${source.url}`);
  }
}

function productSearchText(product: ProductGuide): string {
  const walkthroughText = product.walkthrough
    ? product.walkthrough.steps.flatMap((step) => [
        step.title,
        step.action,
        ...(step.items ?? []),
        ...(step.links?.flatMap((link) => [link.label, link.url]) ?? []),
        step.result,
        step.trouble ?? "",
      ])
    : [];
  return [
    product.title,
    product.description,
    ...walkthroughText,
    ...product.buyingChecklist,
    ...product.verificationChecklist,
    ...product.riskNotes,
    ...product.faq.flatMap((item) => [item.question, item.answer]),
  ].join("\n");
}

export function validateGuideRegistry(registry: GuideRegistry): void {
  const brandValues = Object.values(registry.brands);
  const productValues = Object.values(registry.products);
  const deliveryValues = Object.values(registry.delivery);
  const generalValues = Object.values(registry.general);

  assertExactKeys(Object.keys(registry.brands), BRAND_SLUGS, "brand guide");
  assertExactKeys(Object.keys(registry.products), PRODUCT_SLUGS, "product guide");
  assertExactKeys(Object.keys(registry.delivery), KNOWN_DELIVERY_TYPES, "delivery guide");
  assertExactKeys(Object.keys(registry.general), GENERAL_GUIDE_SLUGS, "general guide");

  assertUnique(brandValues.map((guide) => guide.brand), "brand slug");
  assertUnique(productValues.map((guide) => guide.productSlug), "product slug");
  assertUnique(deliveryValues.map((guide) => guide.deliveryType), "delivery slug");
  assertUnique(generalValues.map((guide) => guide.slug), "general guide slug");

  for (const [key, guide] of Object.entries(registry.brands)) {
    assert(key === guide.brand, `brand key ${key} does not match guide brand ${guide.brand}`);
    assert(guide.title.trim(), `brand ${guide.brand} is missing title`);
    assert(guide.description.trim(), `brand ${guide.brand} is missing description`);
    assert(guide.lastReviewedAt.trim(), `brand ${guide.brand} is missing lastReviewedAt`);
    validateSources(guide.officialSources, `brand ${guide.brand}`);
    for (const productSlug of guide.productSlugs) {
      assert(Boolean(registry.products[productSlug]), `brand ${guide.brand} references missing product ${productSlug}`);
      assert(registry.products[productSlug].brand === guide.brand, `product ${productSlug} belongs to the wrong brand`);
    }
  }

  const accountDeliveryTypes = new Set(["finished_account", "semi_finished_account", "team_seat", "shared_pool", "trial_account"]);
  const apiProductSlugs = new Set(["openai-api-credit", "claude-api-access", "gemini-api-access", "grok-api-access"]);

  for (const [key, product] of Object.entries(registry.products)) {
    assert(key === product.productSlug, `product key ${key} does not match product slug ${product.productSlug}`);
    assert(product.title.trim(), `product ${product.productSlug} is missing title`);
    assert(product.description.trim(), `product ${product.productSlug} is missing description`);
    assert(product.lastReviewedAt.trim(), `product ${product.productSlug} is missing lastReviewedAt`);
    assert(product.audience.length > 0, `product ${product.productSlug} is missing audience`);
    assert(product.buyingChecklist.length > 0, `product ${product.productSlug} is missing buying checklist`);
    assert(product.verificationChecklist.length > 0, `product ${product.productSlug} is missing verification checklist`);
    assert(product.riskNotes.length > 0, `product ${product.productSlug} is missing risk notes`);
    assert(product.faq.length > 0, `product ${product.productSlug} is missing FAQ`);
    validateSources(product.officialSources, `product ${product.productSlug}`);

    if (product.walkthrough) {
      assert(product.walkthrough.title.trim(), `product ${product.productSlug} walkthrough is missing title`);
      assert(product.walkthrough.intro.trim(), `product ${product.productSlug} walkthrough is missing intro`);
      assert(product.walkthrough.steps.length >= 4, `product ${product.productSlug} walkthrough must include at least four steps`);
      for (const step of product.walkthrough.steps) {
        assert(step.title.trim(), `product ${product.productSlug} walkthrough has a step without title`);
        assert(step.action.trim(), `product ${product.productSlug} walkthrough has a step without action`);
        assert(step.result.trim(), `product ${product.productSlug} walkthrough has a step without result`);
        for (const item of step.items ?? []) {
          assert(item.trim(), `product ${product.productSlug} walkthrough has an empty substep`);
        }
        for (const link of step.links ?? []) {
          assert(link.label.trim(), `product ${product.productSlug} walkthrough has a link without label`);
          if (link.url.startsWith("/") && !link.url.startsWith("//")) continue;
          let url: URL;
          try {
            url = new URL(link.url);
          } catch {
            throw new Error(`Invalid guide registry: product ${product.productSlug} walkthrough has an invalid link: ${link.url}`);
          }
          assert(url.protocol === "https:", `product ${product.productSlug} walkthrough link must use HTTPS: ${link.url}`);
        }
      }
    }

    assertUnique(product.supportedDeliveryTypes, `delivery type in product ${product.productSlug}`);
    for (const deliveryType of product.supportedDeliveryTypes) {
      assert(Boolean(registry.delivery[deliveryType]), `product ${product.productSlug} references missing delivery ${deliveryType}`);
    }

    const searchText = productSearchText(product);
    if (apiProductSlugs.has(product.productSlug)) {
      assert(/API Key/i.test(searchText), `API product ${product.productSlug} is missing API Key guidance`);
      assert(/公开代码|公开仓库|前端/.test(searchText), `API product ${product.productSlug} is missing public-code warning`);
      assert(/环境变量|密钥管理/.test(searchText), `API product ${product.productSlug} is missing secret-management guidance`);
      assert(/撤销/.test(searchText), `API product ${product.productSlug} is missing Key revocation guidance`);
    }

    if (product.supportedDeliveryTypes.some((deliveryType) => accountDeliveryTypes.has(deliveryType))) {
      assert(/控制权/.test(searchText), `account product ${product.productSlug} is missing control guidance`);
      assert(/隐私/.test(searchText), `account product ${product.productSlug} is missing privacy guidance`);
    }
  }

  for (const [key, guide] of Object.entries(registry.delivery)) {
    assert(key === guide.deliveryType, `delivery key ${key} does not match delivery type ${guide.deliveryType}`);
    assert(guide.deliveryType !== ("unknown" as string), "unknown must not have a delivery guide");
    assert(guide.title.trim(), `delivery ${guide.deliveryType} is missing title`);
    assert(guide.summary.trim(), `delivery ${guide.deliveryType} is missing summary`);
    assert(guide.lastReviewedAt.trim(), `delivery ${guide.deliveryType} is missing lastReviewedAt`);
    assert(guide.riskNotes.length > 0, `delivery ${guide.deliveryType} is missing risk notes`);
    validateSources(guide.officialSources, `delivery ${guide.deliveryType}`);
  }

  const apiGuideText = JSON.stringify(registry.delivery.api_credit);
  assert(/API Key/i.test(apiGuideText) && /公开代码|前端|公开仓库/.test(apiGuideText), "api_credit is missing public-code Key guidance");
  assert(/环境变量|密钥管理/.test(apiGuideText) && /撤销/.test(apiGuideText), "api_credit is missing secret storage or revocation guidance");

  const finishedAccountText = JSON.stringify(registry.delivery.finished_account);
  assert(/控制权/.test(finishedAccountText) && /隐私|敏感/.test(finishedAccountText), "finished_account is missing control or privacy guidance");

  const sharedPoolText = JSON.stringify(registry.delivery.shared_pool);
  assert(/敏感/.test(sharedPoolText) && /隐私/.test(sharedPoolText), "shared_pool is missing sensitive-data warning");

  const relayText = JSON.stringify(registry.delivery.relay_api);
  assert(/第三方/.test(relayText) && /处理|服务器/.test(relayText) && /数据|输入|输出/.test(relayText), "relay_api is missing third-party data handling warning");

  for (const [key, guide] of Object.entries(registry.general)) {
    assert(key === guide.slug, `general key ${key} does not match guide slug ${guide.slug}`);
    assert(guide.title.trim(), `general guide ${guide.slug} is missing title`);
    assert(guide.description.trim(), `general guide ${guide.slug} is missing description`);
    assert(guide.lastReviewedAt.trim(), `general guide ${guide.slug} is missing lastReviewedAt`);
    validateSources(guide.officialSources, `general guide ${guide.slug}`);
  }
}
