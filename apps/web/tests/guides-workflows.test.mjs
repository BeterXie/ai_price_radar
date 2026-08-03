import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { getWorkflowGuide, guideRegistry } from "../lib/guides/registry.ts";
import { WORKFLOW_GUIDE_SLUGS } from "../lib/guides/types.ts";

const workflowValues = Object.values(guideRegistry.workflows);

function workflowSearchText(workflow) {
  return JSON.stringify(workflow);
}

test("workflow registry contains all expected workflow slugs", () => {
  assert.deepEqual(Object.keys(guideRegistry.workflows).sort(), [...WORKFLOW_GUIDE_SLUGS].sort());
});

test("all OpenAI products reference at least one valid workflow", () => {
  for (const product of Object.values(guideRegistry.products)) {
    if (product.brand !== "openai") continue;
    assert.ok(product.workflowReferences && product.workflowReferences.length > 0, product.productSlug);
    for (const reference of product.workflowReferences) {
      assert.ok(getWorkflowGuide(reference.workflowSlug), `${product.productSlug}: ${reference.workflowSlug}`);
    }
  }
});

test("non-OpenAI products do not reference OpenAI workflows", () => {
  for (const product of Object.values(guideRegistry.products)) {
    if (product.brand === "openai") continue;
    assert.ok(!product.workflowReferences || product.workflowReferences.length === 0, product.productSlug);
  }
});

test("product workflow references are unique", () => {
  for (const product of Object.values(guideRegistry.products)) {
    const references = product.workflowReferences ?? [];
    const slugs = references.map((reference) => reference.workflowSlug);
    assert.equal(new Set(slugs).size, slugs.length, product.productSlug);
  }
});

test("cockpit workflow includes CC Switch and Codex++ variants", () => {
  const workflow = guideRegistry.workflows["cockpit-to-codex"];
  assert.ok(workflow.variants.some((variant) => variant.id === "cc-switch"));
  assert.ok(workflow.variants.some((variant) => variant.id === "codex-plusplus"));
});

test("sub2api workflow includes CC Switch and Codex++ variants", () => {
  const workflow = guideRegistry.workflows["sub2api-to-codex"];
  assert.ok(workflow.variants.some((variant) => variant.id === "cc-switch"));
  assert.ok(workflow.variants.some((variant) => variant.id === "codex-plusplus"));
});

test("direct endpoint workflow includes CC Switch and Codex++ variants", () => {
  const workflow = guideRegistry.workflows["api-endpoint-to-codex"];
  assert.ok(workflow.variants.some((variant) => variant.id === "cc-switch"));
  assert.ok(workflow.variants.some((variant) => variant.id === "codex-plusplus"));
});

test("CC Switch points to farion1231/cc-switch", () => {
  const source = workflowValues
    .flatMap((workflow) => workflow.sources)
    .find((source) => source.title === "CC Switch");
  assert.equal(source?.url, "https://github.com/farion1231/cc-switch");
});

test("Codex++ points to BigPizzaV3/CodexPlusPlus", () => {
  const source = workflowValues
    .flatMap((workflow) => workflow.sources)
    .find((source) => source.title === "CodexPlusPlus");
  assert.equal(source?.url, "https://github.com/BigPizzaV3/CodexPlusPlus");
});

test("blacklisted CC Switch and codex-plusplus URLs are absent", () => {
  const content = JSON.stringify(guideRegistry);
  assert.doesNotMatch(content, /ccswitch\.cc/);
  assert.doesNotMatch(content, /github\.com\/b-nnett\/codex-plusplus/i);
});

test("every workflow warns against exposing credentials", () => {
  for (const workflow of workflowValues) {
    const text = workflowSearchText(workflow);
    assert.match(text, /第三方/, workflow.slug);
    assert.match(text, /凭证|密钥/, workflow.slug);
    assert.match(text, /不要上传|不要公开/, workflow.slug);
  }
});

test("sub2api workflow distinguishes admin keys from user keys", () => {
  const text = workflowSearchText(guideRegistry.workflows["sub2api-to-codex"]);
  assert.match(text, /HTTPS/);
  assert.match(text, /管理员 Key/);
  assert.match(text, /用户 Key/);
});

test("team and K12 products include administrator revocation warning", () => {
  for (const slug of ["chatgpt-k12", "codex-access"]) {
    const references = guideRegistry.products[slug].workflowReferences ?? [];
    assert.ok(references.length > 0, slug);
    assert.ok(references.some((reference) => /管理员/.test(reference.note ?? "")), slug);
  }
});

test("all product workflow links resolve", () => {
  for (const product of Object.values(guideRegistry.products)) {
    for (const reference of product.workflowReferences ?? []) {
      assert.ok(getWorkflowGuide(reference.workflowSlug), `${product.productSlug} -> ${reference.workflowSlug}`);
      assert.match(`/guides/workflows/${reference.workflowSlug}`, /^\/guides\/workflows\//);
    }
  }
});

test("all workflow pages are included in sitemap", async () => {
  const sitemapPath = fileURLToPath(new URL("../app/sitemap.ts", import.meta.url));
  const source = await readFile(sitemapPath, "utf8");
  assert.match(source, /workflowGuides/);
  assert.match(source, /\/guides\/workflows\//);
  for (const slug of WORKFLOW_GUIDE_SLUGS) {
    assert.ok(source.includes(`workflows/${slug}`) || source.includes(`encodeURIComponent(slug)`), slug);
  }
});

test("guide search data includes Cockpit Sub2API CC Switch and Codex++", async () => {
  const pagePath = fileURLToPath(new URL("../app/guides/page.tsx", import.meta.url));
  const source = await readFile(pagePath, "utf8");
  for (const keyword of ["Cockpit", "Sub2API", "CC Switch", "Codex++", "OpenAI 与 Codex 使用工作流"]) {
    assert.ok(source.includes(keyword), keyword);
  }
});
