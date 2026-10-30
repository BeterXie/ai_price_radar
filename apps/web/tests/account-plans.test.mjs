import assert from "node:assert/strict";
import test from "node:test";
import { BRAND_TABS, PRODUCT_TABS } from "../lib/catalog.ts";

test("official plan filters exclude merchant labels and uncertain tiers", () => {
  assert.deepEqual(PRODUCT_TABS.OpenAI.filter((tab) => !tab.other).map((tab) => tab.label), [
    "Free", "Plus", "Go", "Pro 100 / 5x", "Pro 200 / 20x", "Pro 500", "Business / Team", "Edu", "Enterprise",
  ]);
  assert.deepEqual(PRODUCT_TABS.Claude.filter((tab) => !tab.other).map((tab) => tab.label), [
    "Pro", "Max 5x", "Max 20x", "Team", "Enterprise",
  ]);
});

test("MUSE and JEV have separate filters without invented official plans", () => {
  for (const brand of ["MUSE", "JEV"]) {
    assert.ok(BRAND_TABS.includes(brand));
    const tabs = PRODUCT_TABS[brand];
    assert.ok(tabs.every((tab) => tab.other));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-account`));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-invite`));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-api-credit`));
  }
});
