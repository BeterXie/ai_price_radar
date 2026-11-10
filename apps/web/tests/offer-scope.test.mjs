import assert from "node:assert/strict";
import test from "node:test";

import { filterValues, offerQuery } from "../components/product-workspace.tsx";
import { OfferScopeControls } from "../components/offer-scope-controls.tsx";
import { hasNarrowingFilters, ProductCatalogPage } from "../components/product-catalog-page.tsx";
import { BRAND_TABS, PRODUCT_TABS, ALL_PRODUCTS } from "../lib/catalog.ts";
import { buildSearchHref } from "../lib/search.ts";
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
  assert.equal(hasNarrowingFilters({ q: "Max5x" }), true);
  assert.equal(hasNarrowingFilters({ q: " \u200b " }), false);
});

test("catalog filtering retains search, source, brand and offer filters", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify(
      String(url).includes("/meta")
        ? { platforms: [], brands: [], source_platforms: [], product_types: [], tags: [] }
        : { items: [], total: 0, page: 1, page_size: 30 }
    ), { status: 200 });
  });
  const tree = await ProductCatalogPage({ rawParams: { brand: "Claude", source_platform: "16688", in_stock: "true", period: "one_month", q: "Max" } });
  const nodes = catalogDescendants(tree);
  const filters = nodes.find((node) => node.type?.name === "OfferScopeControls");
  assert.ok(filters);
  assert.equal(filters.props.hiddenFields.source_platform, "16688");
  assert.equal(filters.props.hiddenFields.brand, "Claude");
  assert.equal(filters.props.hiddenFields.q, "Max");
  assert.equal(filters.props.values.in_stock, "true");
  assert.equal(filters.props.values.period, "one_month");
  const request = new URL(calls.find((url) => url.includes("/catalog/groups")));
  for (const [key, value] of Object.entries({ brand: "Claude", source_platform: "16688", in_stock: "true", period: "one_month", q: "Max" })) {
    assert.equal(request.searchParams.get(key), value);
  }
});

test("catalog and product search submission and clearing retain the current scope", () => {
  for (const action of ["/products", "/products/claude-pro"]) {
    const hiddenFields = { q: "Max 微风", source_platform: "16688", ...(action === "/products" ? { brand: "Claude" } : {}) };
    const values = filterValues({ comparable: "false", in_stock: "true", period: "one_month", min_price: "25" });
    const nodes = catalogDescendants(OfferScopeControls({ action, values, hiddenFields, resetHref: "/products?q=Max" }));
    const search = nodes.find((node) => node.type?.name === "SearchBox");
    assert.ok(search);
    assert.equal(search.props.defaultValue, "Max 微风");
    const href = buildSearchHref(search.props.action, "", search.props.filters);
    const url = assertCatalogScope({ props: { href } }, { source_platform: "16688", comparable: "false", in_stock: "true", period: "one_month", min_price: "25" });
    assert.equal(url.pathname, action);
    assert.equal(url.searchParams.has("q"), false);
    assert.equal(url.searchParams.get("brand"), action === "/products" ? "Claude" : null);
  }
  const unfiltered = catalogDescendants(OfferScopeControls({ action: "/products", values: filterValues({}), resetHref: "/products" }));
  assert.equal(unfiltered.find((node) => node.type?.name === "SearchBox")?.props.defaultValue, "");
});

test("account and recharge switches retain scope and the detailed filter retains the account group", () => {
  for (const action of ["/products", "/brands/claude", "/products/claude-pro"]) {
    const values = filterValues({ delivery_type: "account", period: "one_month", in_stock: "true" });
    const tree = OfferScopeControls({ action, values, hiddenFields: { q: "微风", source_platform: "16688" }, resetHref: action });
    const nodes = catalogDescendants(tree);
    const links = catalogDescendants(nodes.find((node) => node.props?.className === "offer-delivery-switch"))
      .filter((node) => typeof node.props?.href === "string");
    assert.deepEqual(links.map((link) => link.props.children), ["全部", "账号", "代充"]);
    assert.equal(links[1].props["aria-current"], "page");
    for (const [index, delivery] of ["", "account", "subscription_recharge"].entries()) {
      const url = assertCatalogScope(links[index], { comparable: "true", period: "one_month", in_stock: "true", q: "微风", source_platform: "16688" });
      assert.equal(url.pathname, action);
      assert.equal(url.searchParams.get("delivery_type") || "", delivery);
    }
    const form = nodes.find((node) => node.type?.name === "FilterForm");
    const select = catalogDescendants(form.type(form.props)).find((node) => node.type === "select" && node.props.name === "delivery_type");
    assert.equal(select.props.defaultValue, "account");
    const options = catalogDescendants(select).filter((node) => node.type === "option").map((node) => node.props.value);
    for (const delivery of ["account", "finished_account", "semi_finished_account"]) assert.ok(options.includes(delivery));
    assert.equal(offerQuery({ delivery_type: "account" }).get("delivery_type"), "account");
  }
});

test("every brand has a scoped search in the filter toolbar", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => new Response(JSON.stringify(
    String(url).includes("/meta") ? mockCatalogMetadata() : { items: [], total: 0, page: 1, page_size: 30 }
  ), { status: 200 }));
  for (const brand of ["", ...BRAND_TABS]) {
    const page = await ProductCatalogPage({ rawParams: { brand } });
    const filters = catalogDescendants(page).find((node) => node.type?.name === "OfferScopeControls");
    const search = catalogDescendants(OfferScopeControls(filters.props)).find((node) => node.type?.name === "SearchBox");
    assert.ok(search, `${brand || "all brands"} must have a search field`);
    assert.equal(search.props.filters.brand || "", brand);
    assert.equal(search.props.action, "/products");
    const brandLink = catalogLink(catalogDescendants(page), (url) => url.pathname === "/brands/claude");
    assert.equal(new URL(brandLink.props.href, "https://example.test").search, "");
  }
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

const widenedCatalogScope = {
  brand: "Claude",
  source_platform: "independent",
  comparable: "false",
  in_stock: "true",
  delivery_type: "finished_account",
  period: "one_month",
  warranty: "covered",
  auto_delivery: "false",
  updated_within_hours: "24",
  min_price: "25.50",
  max_price: "100",
  q: "Max 微风",
};

function catalogDescendants(node) {
  if (!node || typeof node !== "object") return [];
  // Render the server layout so its navigation slot is checked in the same
  // tree as the quote controls, regardless of the selected brand composition.
  if (node.type?.name === "BrandCatalogFrame") return catalogDescendants(node.type(node.props));
  return [node, ...[node.props?.children].flat(Infinity).flatMap(catalogDescendants)];
}

function catalogLink(nodes, predicate) {
  return nodes.find((node) => typeof node.props?.href === "string" && predicate(new URL(node.props.href, "https://example.test")));
}

function assertCatalogScope(link, expected) {
  assert.ok(link, "expected a catalog navigation link");
  const url = new URL(link.props.href, "https://example.test");
  for (const [key, value] of Object.entries(expected)) {
    assert.equal(url.searchParams.get(key), value, `${url.pathname} must retain ${key}`);
  }
  return url;
}

function mockCatalogMetadata() {
  return {
    platforms: [], brands: [], product_types: [], tags: [],
    source_platforms: [{ id: "independent", label: "独立站点" }, { id: "16688", label: "16688" }],
  };
}

test("brand, source and product navigation retain the widened scope and intersecting filters", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => new Response(JSON.stringify(
    String(url).includes("/meta")
      ? mockCatalogMetadata()
      : { items: [], total: 0, snapshot_id: 42, offer_total: 0, in_stock_count: 0, comparable_offer_count: 0, trusted_offer_count: 0, last_updated_at: null, snapshot_at: null }
  ), { status: 200 }));

  const nodes = catalogDescendants(await ProductCatalogPage({ rawParams: widenedCatalogScope }));
  const brandLink = catalogLink(nodes, (url) => url.pathname === "/brands/gemini");
  const { brand: currentBrand, ...brandScope } = widenedCatalogScope;
  assertCatalogScope(brandLink, brandScope);

  const sourceLink = catalogLink(nodes, (url) => url.pathname === "/products" && url.searchParams.get("source_platform") === "16688");
  assertCatalogScope(sourceLink, { ...widenedCatalogScope, source_platform: "16688" });

  const productLink = catalogLink(nodes, (url) => url.pathname === "/products/claude-pro");
  const { brand, ...productScope } = widenedCatalogScope;
  assertCatalogScope(productLink, productScope);
});

test("catalog failure retry retains the complete current scope", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => {
    if (String(url).includes("/meta")) return new Response(JSON.stringify(mockCatalogMetadata()), { status: 200 });
    return new Response("catalog temporarily unavailable", { status: 503 });
  });

  const nodes = catalogDescendants(await ProductCatalogPage({ rawParams: widenedCatalogScope }));
  const alert = nodes.find((node) => node.props?.role === "alert");
  assert.ok(alert, "catalog failure must expose an error state");
  const retryLink = catalogLink(catalogDescendants(alert), (url) => url.pathname === "/brands/claude");
  const { brand, ...scope } = widenedCatalogScope;
  assertCatalogScope(retryLink, scope);
});

test("empty brand catalog keeps its brand when opening related offers", async (context) => {
  context.mock.method(globalThis, "fetch", async (url) => new Response(JSON.stringify(
    String(url).includes("/meta")
      ? mockCatalogMetadata()
      : { items: [], total: 0, snapshot_id: 42, offer_total: 0, in_stock_count: 0, comparable_offer_count: 0, trusted_offer_count: 0, last_updated_at: null, snapshot_at: null }
  ), { status: 200 }));

  const nodes = catalogDescendants(await ProductCatalogPage({ rawParams: { brand: "Claude" } }));
  const empty = nodes.find((node) => node.props?.className === "catalog-empty");
  assert.ok(empty, "an empty brand catalog must expose its related-offers action");
  const relatedLink = catalogLink(catalogDescendants(empty), (url) => url.pathname === "/brands/claude");
  assertCatalogScope(relatedLink, { comparable: "false" });
});

test("canonical brand pages keep search, source and stock filters on the brand path", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    calls.push(String(url));
    return new Response(JSON.stringify(String(url).includes("/meta") ? mockCatalogMetadata() : { items: [], total: 0 }), { status: 200 });
  });
  const nodes = catalogDescendants(await ProductCatalogPage({ catalogBrand: "Claude", rawParams: { ...widenedCatalogScope, brand: "OpenAI" } }));
  const filters = nodes.find((node) => node.type?.name === "OfferScopeControls");
  assert.equal(filters.props.action, "/brands/claude");
  assert.equal(filters.props.hiddenFields.brand, undefined);
  assert.equal(new URL(calls.find((url) => url.includes("/catalog/groups"))).searchParams.get("brand"), "Claude");
  const sourceLink = catalogLink(nodes, (url) => url.pathname === "/brands/claude" && url.searchParams.get("source_platform") === "16688");
  const { brand, ...scope } = widenedCatalogScope;
  assertCatalogScope(sourceLink, { ...scope, source_platform: "16688" });
  const search = catalogDescendants(OfferScopeControls(filters.props)).find((node) => node.type?.name === "SearchBox");
  const cleared = new URL(buildSearchHref(search.props.action, "", search.props.filters), "https://example.test");
  assert.equal(cleared.pathname, "/brands/claude");
  assert.equal(cleared.searchParams.has("brand"), false);
  assert.equal(cleared.searchParams.has("q"), false);
  assert.equal(cleared.searchParams.get("in_stock"), "true");
});
