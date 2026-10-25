import assert from "node:assert/strict";
import test from "node:test";

import { filterValues, offerQuery } from "../components/product-workspace.tsx";
import { hasNarrowingFilters, ProductCatalogPage } from "../components/product-catalog-page.tsx";
import { BRAND_TABS, PRODUCT_TABS, ALL_PRODUCTS } from "../lib/catalog.ts";
import RelaysPage from "../app/relays/page.tsx";

test("offer scope defaults to directly comparable offers", () => {
  const query = offerQuery({});
  assert.equal(query.get("comparable"), "true");
  assert.equal(filterValues({}).comparable, "true");
});

test("包含相关商品 widens the API scope to every offer instead of only non-comparable ones", () => {
  // Sending comparable=false to the API would return *only* relays / pools /
  // trial accounts, which is never what the "包含相关商品" option promises.
  const query = offerQuery({ comparable: "false", in_stock: "true" });
  assert.equal(query.has("comparable"), false);
  assert.equal(query.get("in_stock"), "true");
  // The select still shows the widened option.
  assert.equal(filterValues({ comparable: "false" }).comparable, "false");
});

test("narrowing filters are detected independently of the comparable scope", () => {
  assert.equal(hasNarrowingFilters({}), false);
  assert.equal(hasNarrowingFilters({ comparable: "false" }), false);
  assert.equal(hasNarrowingFilters({ delivery_type: "relay_api" }), true);
  assert.equal(hasNarrowingFilters({ in_stock: "true" }), true);
  assert.equal(hasNarrowingFilters({ source_platform: "ldxp" }), true);
});

test("catalog search retains source, brand and offer filters", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => new Response(JSON.stringify(
    String(url).includes("/meta")
      ? { platforms: [], brands: [], source_platforms: [], product_types: [], tags: [] }
      : { items: [], total: 0, page: 1, page_size: 30 }
  ), { status: 200 }));
  const tree = await ProductCatalogPage({ rawParams: { brand: "Claude", source_platform: "16688", in_stock: "true", period: "one_month", q: "Max" } });
  function findSearch(node) {
    if (!node || typeof node !== "object") return null;
    if (node.type?.name === "SearchBox") return node;
    const children = node.props?.children;
    for (const child of Array.isArray(children) ? children.flat(Infinity) : [children]) {
      const found = findSearch(child);
      if (found) return found;
    }
    return null;
  }
  const search = findSearch(tree);
  assert.ok(search);
  assert.equal(search.props.filters.source_platform, "16688");
  assert.equal(search.props.filters.brand, "Claude");
  assert.equal(search.props.filters.in_stock, "true");
  assert.equal(search.props.filters.period, "one_month");
});

test("智谱 is no longer a public brand tab and 中转站 is not a crawled brand", () => {
  assert.equal(BRAND_TABS.includes("智谱"), false);
  assert.equal(BRAND_TABS.includes("中转站"), false);
  assert.equal(Object.keys(PRODUCT_TABS).includes("智谱"), false);
  assert.equal(ALL_PRODUCTS.some((product) => product.slug.startsWith("zhipu-")), false);
});

test("catalog relay tab and top-level relay entry share live station data and view controls", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify(String(url).includes("/relays")
      ? { enabled: true, items: [{ id: 42, name: "Live relay" }] }
      : { relay_hub_enabled: true }), { status: 200 });
  });
  const catalog = await ProductCatalogPage({ rawParams: { brand: "中转站", view: "card", in_stock: "true" } });
  const shortcut = await (RelaysPage.default || RelaysPage)({ searchParams: Promise.resolve({ view: "card" }) });
  assert.equal(catalog.type.name, "RelayCatalogPage");
  assert.equal(shortcut.type.name, "RelayCatalogPage");
  function descendants(node) {
    if (!node || typeof node !== "object") return [];
    return [node, ...[node.props?.children].flat(Infinity).flatMap(descendants)];
  }
  for (const entry of [catalog, shortcut]) {
    const nodes = descendants(await entry.type(entry.props));
    const station = nodes.find((node) => node.type?.name === "RelayStationCard");
    assert.equal(station?.props.station.id, 42);
    assert.equal(station?.props.view, "card");
    const list = nodes.find((node) => node.props?.["aria-label"] === "列表展示");
    const listUrl = new URL(list.props.href, "https://ai.pricememo.cn");
    assert.equal(listUrl.pathname, entry.props.basePath);
    assert.equal(listUrl.searchParams.get("brand"), entry.props.basePath === "/products" ? "中转站" : null);
    assert.equal(listUrl.searchParams.has("in_stock"), false);
    assert.equal(nodes.filter((node) => node.props?.["aria-current"] === "page").length, 1);
  }
  assert.equal(calls.filter((url) => url.includes("/api/v1/relays")).length, 2);
  assert.equal(calls.some((url) => url.includes("/catalog/groups")), false);
});
