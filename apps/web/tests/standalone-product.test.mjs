import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { BRAND_TABS, PRODUCT_CATEGORIES, PRODUCT_TABS, ALL_PRODUCTS } from "../lib/catalog.ts";
import { normalizeProductIdentity } from "../lib/product-identity.ts";
import { PlatformIcon } from "../components/platform-icon.tsx";
import { ProductCatalogPage } from "../components/product-catalog-page.tsx";

function descendants(node) {
  if (!node || typeof node !== "object") return [];
  return [node, ...[node.props?.children].flat(Infinity).flatMap(descendants)];
}

const legacyProduct = {
  slug: "chatgpt-access-service", platform: "OpenAI", brand: "OpenAI", display_name: "ChatGPT 手机接码",
  subtitle: "适用于 ChatGPT / OpenAI 的注册验证", product_type: "service", price_currency: "CNY",
  lowest_price: "5.00", related_lowest_price: null, offer_count: 1, in_stock_count: 1,
  comparable_offer_count: 1, trusted_offer_count: 1, median_price: "5.00", source_count: 1,
  data_quality_score: 50, data_quality_label: "一般", official_reference: null, last_updated_at: null, tags: [],
  highest_price: "5.00", offer_group_count: 1, price_breakdown: [], snapshot_id: 42, snapshot_at: null,
  offers: [], offer_groups: [], history: [], trend: [], description: "验证辅助服务",
};

test("phone verification is its own product category, not an OpenAI plan", () => {
  assert.ok(BRAND_TABS.includes("OpenAI"));
  assert.ok(PRODUCT_CATEGORIES.includes("手机接码"));
  assert.equal(PRODUCT_TABS.OpenAI.some((item) => item.slug === "chatgpt-access-service"), false);
  assert.deepEqual(PRODUCT_TABS["手机接码"].map((item) => item.slug), ["chatgpt-access-service"]);
  assert.deepEqual(ALL_PRODUCTS.filter((item) => item.slug === "chatgpt-access-service").map((item) => item.brand), ["手机接码"]);
});

test("old product links and snapshots resolve to the standalone phone service identity", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const request = String(url);
    calls.push(request);
    const data = request.includes("/meta")
      ? { platforms: ["OpenAI", "手机接码"], brands: ["OpenAI", "手机接码"], source_platforms: [], product_types: [], tags: [] }
      : legacyProduct;
    return new Response(JSON.stringify(data), { status: 200 });
  });
  const tree = await ProductCatalogPage({ rawParams: { brand: "手机接码", comparable: "true" } });
  const workspace = descendants(tree).find((node) => node.type?.name === "ProductWorkspace");
  assert.ok(workspace, "the independent category resolves the stable existing product");
  assert.equal(workspace.props.product.slug, "chatgpt-access-service");
  assert.equal(workspace.props.product.brand, "手机接码");
  assert.equal(workspace.props.product.display_name, "手机接码");
  assert.ok(calls.some((url) => url.includes("/products/chatgpt-access-service?comparable=true")));
  const normalized = normalizeProductIdentity(legacyProduct);
  assert.equal(normalized.slug, legacyProduct.slug);
  assert.equal(normalized.display_name, "手机接码");
  assert.equal(normalized.brand, "手机接码");
  assert.equal(normalized.lowest_price, legacyProduct.lowest_price);
  assert.equal(normalized.offer_count, legacyProduct.offer_count);
});

test("MUSE and JEV use monochrome masks derived from their verified logos", () => {
  const muse = descendants(createElement(PlatformIcon, { platform: "MUSE", size: 26 }))[0];
  const jev = descendants(createElement(PlatformIcon, { platform: "JEV", size: 26 }))[0];
  const museMark = PlatformIcon({ platform: "MUSE", size: 26 });
  const jevMark = PlatformIcon({ platform: "JEV", size: 26 });
  const renderedMuse = museMark.type(museMark.props);
  const renderedJev = jevMark.type(jevMark.props);
  assert.equal(renderedMuse.props.style.WebkitMask, "url(/brand/muse-mark.png) center / contain no-repeat");
  assert.equal(renderedJev.props.style.WebkitMask, "url(/brand/jev-mark.png) center / contain no-repeat");
  assert.equal(renderedMuse.props.className, renderedJev.props.className);
  assert.equal(muse.props.platform, "MUSE");
  assert.equal(jev.props.platform, "JEV");
});
