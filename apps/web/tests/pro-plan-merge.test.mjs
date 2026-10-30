import assert from "node:assert/strict";
import test from "node:test";

import { ALL_PRODUCTS, PRODUCT_TABS, canonicalProductSlug } from "../lib/catalog.ts";
import { getProductSeoContent, getProductOgTitle } from "../lib/product-seo.ts";
import { getProductGuide } from "../lib/guides/registry.ts";
import { resolveGuideHref } from "../lib/guides/matcher.ts";
import ProductPage from "../app/products/[slug]/page.tsx";
import ProductsPage from "../app/products/page.tsx";
import SourceProductPage, { generateMetadata as sourceMetadata } from "../app/sources/[source]/products/[slug]/page.tsx";
import ProductGuidePage, { generateMetadata as guideMetadata, generateStaticParams } from "../app/guides/products/[productSlug]/page.tsx";

const aliases = [
  ["chatgpt-pro-5x", "chatgpt-pro-100", "Pro 100 / 5x"],
  ["chatgpt-pro-20x", "chatgpt-pro-200", "Pro 200 / 20x"],
];
const filters = {
  source_platform: "16688", comparable: "false", in_stock: "true", period: "one_month",
  delivery_type: "finished_account", warranty: "subscription_term", min_price: "25.50",
  max_price: "100", q: "Pro 独享", tag: ["one", "two"], empty: "", missing: undefined,
};

function render(page, props) {
  return (page.default || page)(props);
}

function descendants(node) {
  if (!node || typeof node !== "object") return [];
  return [node, ...[node.props?.children].flat(Infinity).flatMap(descendants)];
}

async function assertRedirect(run, pathname, expected = filters) {
  await assert.rejects(run, (error) => {
    assert.match(error.digest || "", /^NEXT_REDIRECT;/);
    assert.match(error.digest, /;308;$/);
    const url = new URL(error.digest.split(";")[2], "https://example.test");
    assert.equal(url.pathname, pathname);
    for (const [key, value] of Object.entries(expected)) {
      assert.deepEqual(url.searchParams.getAll(key), value === undefined ? [] : Array.isArray(value) ? value : [value], key);
    }
    return true;
  });
}

test("Pro aliases have one canonical tab each and never appear under other products", () => {
  for (const [legacy, canonical, label] of aliases) {
    assert.equal(canonicalProductSlug(legacy), canonical);
    assert.equal(canonicalProductSlug(canonical), canonical);
    assert.equal(ALL_PRODUCTS.some((item) => item.slug === legacy), false);
    assert.deepEqual(PRODUCT_TABS.OpenAI.filter((tab) => canonicalProductSlug(tab.slug) === canonical), [{ label, slug: canonical }]);
  }
  assert.equal(new Set(PRODUCT_TABS.OpenAI.map((tab) => canonicalProductSlug(tab.slug))).size, PRODUCT_TABS.OpenAI.length);
  for (const slug of ["chatgpt-pro", "chatgpt-pro-500", "claude-pro-20x", "__proto__", "constructor", "unknown"]) {
    assert.equal(canonicalProductSlug(slug), slug);
  }
});

test("legacy product and source paths permanently redirect with every query value", async (context) => {
  context.mock.method(globalThis, "fetch", async () => { throw new Error("redirects must precede API reads"); });
  for (const [legacy, canonical] of aliases) {
    await assertRedirect(
      () => render(ProductPage, { params: Promise.resolve({ slug: legacy }), searchParams: Promise.resolve(filters) }),
      `/products/${canonical}`,
    );
    await assertRedirect(
      () => render(SourceProductPage, { params: Promise.resolve({ source: "16688", slug: legacy }), searchParams: Promise.resolve(filters) }),
      `/sources/16688/products/${canonical}`,
    );
    await assertRedirect(
      () => render(ProductsPage, { searchParams: Promise.resolve({ ...filters, product: legacy, platform: "OpenAI" }) }),
      `/products/${canonical}`, { ...filters, product: undefined, platform: undefined },
    );
    const canonicalPage = await render(ProductPage, { params: Promise.resolve({ slug: canonical }), searchParams: Promise.resolve(filters) });
    assert.equal(canonicalPage.props.productSlug, canonical);
    assert.deepEqual(canonicalPage.props.rawParams, filters);
  }
});

test("canonical source pages apply retained filters and expose canonical metadata", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const request = new URL(String(url));
    calls.push(request);
    const data = request.pathname.endsWith("/meta")
      ? { source_platforms: [{ id: "16688" }] }
      : { slug: "chatgpt-pro-100", display_name: "ChatGPT Pro 100", brand: "OpenAI", offer_count: 2, offer_group_count: 1, offer_groups: [] };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  const tree = await render(SourceProductPage, {
    params: Promise.resolve({ source: "16688", slug: "chatgpt-pro-100" }),
    searchParams: Promise.resolve({ ...filters, source_platform: "independent" }),
  });
  const table = descendants(tree).find((node) => node.type?.name === "OfferGroupTable");
  const query = new URLSearchParams(table.props.filterQuery);
  assert.equal(query.get("source_platform"), "16688");
  assert.equal(query.get("period"), "one_month");
  assert.equal(query.get("in_stock"), "true");
  assert.equal(query.get("q"), filters.q);
  assert.equal(query.has("comparable"), false);
  const request = calls.find((url) => url.pathname.endsWith("/chatgpt-pro-100"));
  assert.equal(request.search, `?${table.props.filterQuery}`);
  const metadata = await sourceMetadata({ params: Promise.resolve({ source: "16688", slug: "chatgpt-pro-5x" }) });
  assert.equal(metadata.alternates.canonical, "https://ai.pricememo.cn/sources/16688/products/chatgpt-pro-100");
  const unfiltered = await render(SourceProductPage, {
    params: Promise.resolve({ source: "16688", slug: "chatgpt-pro-100" }), searchParams: Promise.resolve({}),
  });
  const unfilteredTable = descendants(unfiltered).find((node) => node.type?.name === "OfferGroupTable");
  assert.equal(unfilteredTable.props.filterQuery, "source_platform=16688");
});

test("legacy guide URLs stay readable while metadata, offer links and SEO use canonical plans", async () => {
  const staticSlugs = generateStaticParams().map((item) => item.productSlug);
  for (const [legacy, canonical, label] of aliases) {
    const guide = getProductGuide(legacy);
    assert.equal(guide, getProductGuide(canonical));
    assert.equal(guide.productSlug, canonical);
    assert.equal(guide.offerPath, `/products/${canonical}`);
    assert.equal(guide.title, `ChatGPT ${label} 指南`);
    assert.ok(staticSlugs.includes(canonical));
    assert.equal(staticSlugs.includes(legacy), false);
    assert.equal(resolveGuideHref({ productSlug: legacy, deliveryType: "finished_account" }), `/guides/products/${canonical}#delivery-finished_account`);
    const props = { params: Promise.resolve({ productSlug: legacy }) };
    const metadata = await guideMetadata(props);
    assert.equal(metadata.alternates.canonical, `https://ai.pricememo.cn/guides/products/${canonical}`);
    const tree = await render(ProductGuidePage, props);
    const layout = descendants(tree).find((node) => node.type?.name === "GuideLayout");
    assert.ok(descendants(layout.props.footer).some((node) => node.props?.href === `/products/${canonical}`));
    const seo = getProductSeoContent(canonical, "unused", "unused");
    assert.equal(getProductSeoContent(legacy, "unused", "unused"), seo);
    assert.ok(seo.metaDescription.includes(label));
    assert.equal(getProductOgTitle(legacy), `ChatGPT ${label}`);
  }
});
