import assert from "node:assert/strict";
import test from "node:test";
import { buildSearchHref, normalizeSearchQuery } from "../lib/search.ts";

test("search normalizes pasted full-width text, whitespace and invisible characters", () => {
  assert.equal(normalizeSearchQuery("  Ｃｌａｕｄｅ\u200b\u3000Ｍａｘ５ｘ\n微风  "), "Claude Max5x 微风");
  assert.equal(normalizeSearchQuery(" %_ "), "%_");
});

test("search keeps the selected product and filters but resets pagination", () => {
  const url = new URL(buildSearchHref("/products/claude-pro", " Ｍａｘ 微风 ", {
    q: "old", source_platform: "16688", comparable: "false", in_stock: "true", period: "one_month", page: "3", offset: "60", snapshot: "99",
  }), "https://example.test");
  assert.equal(url.pathname, "/products/claude-pro");
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    source_platform: "16688", comparable: "false", in_stock: "true", period: "one_month", q: "Max 微风",
  });
});

test("clearing a query preserves the brand and price range", () => {
  assert.equal(buildSearchHref("/products", " \u200b ", { q: "old", brand: "OpenAI", min_price: "20", max_price: "100" }), "/products?brand=OpenAI&min_price=20&max_price=100");
  assert.equal(buildSearchHref("/products", ""), "/products");
});
