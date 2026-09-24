import assert from "node:assert/strict";
import test from "node:test";

import { filterValues, offerQuery } from "../components/product-workspace.tsx";
import { hasNarrowingFilters } from "../components/product-catalog-page.tsx";
import { BRAND_TABS, PRODUCT_TABS, ALL_PRODUCTS } from "../lib/catalog.ts";

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

test("智谱 is no longer a public brand tab and 中转站 is not a crawled brand", () => {
  assert.equal(BRAND_TABS.includes("智谱"), false);
  assert.equal(BRAND_TABS.includes("中转站"), false);
  assert.equal(Object.keys(PRODUCT_TABS).includes("智谱"), false);
  assert.equal(ALL_PRODUCTS.some((product) => product.slug.startsWith("zhipu-")), false);
});
