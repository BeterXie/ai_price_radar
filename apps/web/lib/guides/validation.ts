import {
  BRAND_SLUGS,
  GENERAL_GUIDE_SLUGS,
  KNOWN_DELIVERY_TYPES,
  PRODUCT_SLUGS,
  WORKFLOW_GUIDE_SLUGS,
  type GuideSource,
  type GuideRegistry,
  type ProductGuide,
  type WorkflowGuide,
  type WorkflowGuideSlug,
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

function validateSources(sources: readonly GuideSource[], label: string): void {
  assert(sources.length > 0, `${label} must include at least one official source`);
  for (const source of sources) {
    assert(source.title.trim(), `${label} has a source without a title`);
    assert(source.publisher.trim(), `${label} has a source without a publisher`);
    assert(source.lastCheckedAt.trim(), `${label} has a source without lastCheckedAt`);
    assert(
      source.kind === "platform_official" || source.kind === "project_official",
      `${label} source ${source.title} has an unknown kind: ${String(source.kind)}`,
    );
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

function workflowSearchText(workflow: WorkflowGuide): string {
  const walkthroughText = workflow.variants.flatMap((variant) =>
    variant.walkthrough.steps.flatMap((step) => [
      step.title,
      step.action,
      ...(step.items ?? []),
      ...(step.links?.flatMap((link) => [link.label, link.url]) ?? []),
      step.result,
      step.trouble ?? "",
    ]),
  );
  return [
    workflow.title,
    workflow.description,
    ...workflow.flow,
    ...workflow.audience,
    ...workflow.prerequisites,
    ...workflow.overview.map((block) => JSON.stringify(block)),
    ...walkthroughText,
    ...workflow.verificationChecklist,
    ...workflow.commonProblems.flatMap((item) => [item.problem, item.likelyCause, item.action]),
    ...workflow.riskNotes,
    ...workflow.faq.flatMap((item) => [item.question, item.answer]),
    ...workflow.sources.flatMap((source) => [source.title, source.url, source.publisher]),
  ].join("\n");
}

function validateWorkflowVariants(workflow: WorkflowGuide): void {
  assertUnique(workflow.variants.map((variant) => variant.id), `variant id in workflow ${workflow.slug}`);
  for (const variant of workflow.variants) {
    assert(variant.title.trim(), `workflow ${workflow.slug} variant ${variant.id} is missing title`);
    assert(variant.description.trim(), `workflow ${workflow.slug} variant ${variant.id} is missing description`);
    assert(variant.walkthrough.title.trim(), `workflow ${workflow.slug} variant ${variant.id} walkthrough is missing title`);
    assert(variant.walkthrough.intro.trim(), `workflow ${workflow.slug} variant ${variant.id} walkthrough is missing intro`);
    assert(variant.walkthrough.steps.length > 0, `workflow ${workflow.slug} variant ${variant.id} walkthrough must include at least one step`);
    for (const step of variant.walkthrough.steps) {
      assert(step.title.trim(), `workflow ${workflow.slug} variant ${variant.id} has a step without title`);
      assert(step.action.trim(), `workflow ${workflow.slug} variant ${variant.id} has a step without action`);
      assert(step.result.trim(), `workflow ${workflow.slug} variant ${variant.id} has a step without result`);
      for (const item of step.items ?? []) {
        assert(item.trim(), `workflow ${workflow.slug} variant ${variant.id} has an empty substep`);
      }
      for (const link of step.links ?? []) {
        assert(link.label.trim(), `workflow ${workflow.slug} variant ${variant.id} has a link without label`);
        if (link.url.startsWith("/") && !link.url.startsWith("//")) continue;
        let url: URL;
        try {
          url = new URL(link.url);
        } catch {
          throw new Error(`Invalid guide registry: workflow ${workflow.slug} variant ${variant.id} has an invalid link: ${link.url}`);
        }
        assert(url.protocol === "https:", `workflow ${workflow.slug} variant ${variant.id} link must use HTTPS: ${link.url}`);
      }
    }
  }
}

export function validateGuideRegistry(registry: GuideRegistry): void {
  const brandValues = Object.values(registry.brands);
  const productValues = Object.values(registry.products);
  const deliveryValues = Object.values(registry.delivery);
  const generalValues = Object.values(registry.general);
  const workflowValues = Object.values(registry.workflows);

  assertExactKeys(Object.keys(registry.brands), BRAND_SLUGS, "brand guide");
  assertExactKeys(Object.keys(registry.products), PRODUCT_SLUGS, "product guide");
  assertExactKeys(Object.keys(registry.delivery), KNOWN_DELIVERY_TYPES, "delivery guide");
  assertExactKeys(Object.keys(registry.general), GENERAL_GUIDE_SLUGS, "general guide");
  assertExactKeys(Object.keys(registry.workflows), WORKFLOW_GUIDE_SLUGS, "workflow guide");

  assertUnique(brandValues.map((guide) => guide.brand), "brand slug");
  assertUnique(productValues.map((guide) => guide.productSlug), "product slug");
  assertUnique(deliveryValues.map((guide) => guide.deliveryType), "delivery slug");
  assertUnique(generalValues.map((guide) => guide.slug), "general guide slug");
  assertUnique(workflowValues.map((guide) => guide.slug), "workflow guide slug");

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

    const workflowReferences = product.workflowReferences ?? [];
    if (product.brand === "openai") {
      assert(workflowReferences.length > 0, `OpenAI product ${product.productSlug} must reference at least one workflow`);
    } else {
      assert(workflowReferences.length === 0, `non-OpenAI product ${product.productSlug} must not reference OpenAI workflows`);
    }
    const referencedWorkflowSlugs = new Set<string>();
    for (const reference of workflowReferences) {
      assert(
        reference.workflowSlug && Boolean(registry.workflows[reference.workflowSlug]),
        `product ${product.productSlug} references missing workflow ${String(reference.workflowSlug)}`,
      );
      assert(reference.condition.trim(), `product ${product.productSlug} workflow reference ${reference.workflowSlug} is missing condition`);
      assert(reference.audience.trim(), `product ${product.productSlug} workflow reference ${reference.workflowSlug} is missing audience`);
      assert(
        reference.relevance === "recommended" || reference.relevance === "conditional" || reference.relevance === "advanced",
        `product ${product.productSlug} workflow reference ${reference.workflowSlug} has an invalid relevance`,
      );
      assert(!referencedWorkflowSlugs.has(reference.workflowSlug), `product ${product.productSlug} references workflow ${reference.workflowSlug} more than once`);
      referencedWorkflowSlugs.add(reference.workflowSlug);
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

  const requiredWorkflowVariants: Partial<Record<WorkflowGuideSlug, readonly string[]>> = {
    "cockpit-to-codex": ["cc-switch", "codex-plusplus"],
    "sub2api-to-codex": ["cc-switch", "codex-plusplus"],
    "api-endpoint-to-codex": ["cc-switch", "codex-plusplus"],
  };

  for (const [key, workflow] of Object.entries(registry.workflows)) {
    assert(key === workflow.slug, `workflow key ${key} does not match guide slug ${workflow.slug}`);
    assert(workflow.title.trim(), `workflow ${workflow.slug} is missing title`);
    assert(workflow.description.trim(), `workflow ${workflow.slug} is missing description`);
    assert(workflow.lastReviewedAt.trim(), `workflow ${workflow.slug} is missing lastReviewedAt`);
    assert(workflow.flow.length >= 3, `workflow ${workflow.slug} must include at least three flow nodes`);
    assert(workflow.audience.length > 0, `workflow ${workflow.slug} is missing audience`);
    assert(workflow.prerequisites.length > 0, `workflow ${workflow.slug} is missing prerequisites`);
    assert(workflow.variants.length > 0, `workflow ${workflow.slug} is missing variants`);
    assert(workflow.verificationChecklist.length > 0, `workflow ${workflow.slug} is missing verification checklist`);
    assert(workflow.commonProblems.length > 0, `workflow ${workflow.slug} is missing common problems`);
    assert(workflow.riskNotes.length > 0, `workflow ${workflow.slug} is missing risk notes`);
    assert(workflow.faq.length > 0, `workflow ${workflow.slug} is missing FAQ`);
    validateSources(workflow.sources, `workflow ${workflow.slug}`);
    assert(
      workflow.sources.some((source) => source.kind === "platform_official"),
      `workflow ${workflow.slug} must include at least one platform_official source`,
    );
    assert(
      workflow.sources.some((source) => source.kind === "project_official"),
      `workflow ${workflow.slug} must include at least one project_official source`,
    );
    validateWorkflowVariants(workflow);

    const required = requiredWorkflowVariants[workflow.slug];
    if (required) {
      for (const variantId of required) {
        assert(
          workflow.variants.some((variant) => variant.id === variantId),
          `workflow ${workflow.slug} must include ${variantId} variant`,
        );
      }
    }
  }

  for (const workflow of workflowValues) {
    const searchText = workflowSearchText(workflow);
    assert(/第三方/.test(searchText), `workflow ${workflow.slug} is missing third-party disclosure`);
    assert(/(凭证|密钥)/.test(searchText), `workflow ${workflow.slug} is missing credential guidance`);
    assert(/(不要上传|不要公开)/.test(searchText), `workflow ${workflow.slug} is missing do-not-upload guidance`);
  }

  const cockpitSearchText = workflowSearchText(registry.workflows["cockpit-to-codex"]);
  assert(/本地/.test(cockpitSearchText), "cockpit workflow is missing local guidance");
  assert(/API 服务/.test(cockpitSearchText), "cockpit workflow is missing API service guidance");
  assert(/Base URL/.test(cockpitSearchText), "cockpit workflow is missing Base URL guidance");

  const sub2apiSearchText = workflowSearchText(registry.workflows["sub2api-to-codex"]);
  assert(/HTTPS/.test(sub2apiSearchText), "sub2api workflow is missing HTTPS guidance");
  assert(/管理员 Key/.test(sub2apiSearchText), "sub2api workflow is missing admin key guidance");
  assert(/用户 Key/.test(sub2apiSearchText), "sub2api workflow is missing user key guidance");

  const allWorkflowSources = workflowValues.flatMap((workflow) => workflow.sources);
  const ccSwitchSource = allWorkflowSources.find((source) => source.title === "CC Switch");
  assert(
    ccSwitchSource?.url === "https://github.com/farion1231/cc-switch",
    "CC Switch must point to https://github.com/farion1231/cc-switch",
  );
  const codexPlusPlusSource = allWorkflowSources.find((source) => source.title === "CodexPlusPlus");
  assert(
    codexPlusPlusSource?.url === "https://github.com/BigPizzaV3/CodexPlusPlus",
    "Codex++ must point to https://github.com/BigPizzaV3/CodexPlusPlus",
  );

  const registryText = JSON.stringify(registry);
  assert(!registryText.includes("ccswitch.cc"), "blacklisted ccswitch.cc URL is present");
  assert(!/github\.com\/b-nnett\/codex-plusplus/i.test(registryText), "blacklisted codex-plusplus URL is present");
}
