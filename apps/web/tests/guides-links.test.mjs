import assert from "node:assert/strict";
import test from "node:test";

import { createGuideMetadata, getGuideCanonicalPath } from "../lib/guides/metadata.ts";
import { guideRegistry } from "../lib/guides/registry.ts";
import { resolveGuideHref } from "../lib/guides/matcher.ts";

test("all source links are HTTPS and all contextual guide links are internal", () => {
  const allGuides = [
    ...Object.values(guideRegistry.brands),
    ...Object.values(guideRegistry.products),
    ...Object.values(guideRegistry.delivery),
    ...Object.values(guideRegistry.general),
  ];
  for (const guide of allGuides) {
    for (const source of guide.officialSources) {
      const url = new URL(source.url);
      assert.equal(url.protocol, "https:", source.url);
      assert.ok(url.hostname.length > 0, source.url);
    }
  }

  for (const product of Object.values(guideRegistry.products)) {
    for (const deliveryType of [...product.supportedDeliveryTypes, "unknown", "invalid"]) {
      assert.match(resolveGuideHref({ productSlug: product.productSlug, deliveryType }), /^\/guides(?:\/|$)/);
    }
  }

  for (const workflow of Object.values(guideRegistry.workflows)) {
    for (const source of workflow.sources) {
      const url = new URL(source.url);
      assert.equal(url.protocol, "https:", source.url);
      assert.ok(url.hostname.length > 0, source.url);
    }
  }
});

test("canonical path helpers cover index, brands, products, delivery, and general pages", () => {
  assert.equal(getGuideCanonicalPath({ kind: "index" }), "/guides");
  assert.equal(getGuideCanonicalPath({ kind: "brand", slug: "openai" }), "/guides/brands/openai");
  assert.equal(getGuideCanonicalPath({ kind: "product", slug: "chatgpt-plus" }), "/guides/products/chatgpt-plus");
  assert.equal(getGuideCanonicalPath({ kind: "delivery", slug: "api_credit" }), "/guides/delivery/api_credit");
  assert.equal(getGuideCanonicalPath({ kind: "general", slug: "security" }), "/guides/security");
});

test("metadata uses the supplied canonical and consistent Open Graph copy", () => {
  const metadata = createGuideMetadata({
    title: "ChatGPT Plus 购买与使用指南",
    description: "测试说明",
    canonicalPath: "/guides/products/chatgpt-plus",
  });
  assert.equal(metadata.title, "ChatGPT Plus 购买与使用指南");
  assert.equal(metadata.description, "测试说明");
  assert.equal(metadata.alternates.canonical, "/guides/products/chatgpt-plus");
  assert.equal(metadata.openGraph.title, metadata.title);
  assert.equal(metadata.openGraph.description, metadata.description);
  assert.equal(metadata.openGraph.url, metadata.alternates.canonical);
});
